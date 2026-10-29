#!/usr/bin/env bash
# Deploy to the shared server: the host Caddy, Prometheus and Grafana live outside this project.
# Steps share one lock, error trap and IMAGE_TAG, so they run only through main, in order.
set -Eeuo pipefail
umask 077

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
export IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse HEAD)}"
if [[ ! "$IMAGE_TAG" =~ ^[0-9a-f]{40}$ ]]; then
  echo "IMAGE_TAG must be a full Git commit SHA." >&2
  exit 1
fi

backup_dir="$HOME/etch-backups"

compose() {
  docker compose -f docker-compose-prod-shared.yml "$@"
}

on_error() {
  local status=$?
  trap - ERR
  echo "Deployment failed: $IMAGE_TAG" >&2
  compose ps -a || true
  compose logs --no-color --tail=40 || true
  exit "$status"
}

# Validate configuration and required files, then fetch the release images.
preflight() {
  compose config --quiet
  test -d backend/certs
  test -f prometheus/metrics_token
  test -f observability/otel-collector-prod.yaml

  # Repair public bind-mounted config permissions from earlier checkouts.
  # The host Prometheus reads metrics_token through its own bind mount.
  chmod 644 \
    observability/otel-collector-prod.yaml \
    observability/loki.yaml \
    observability/tempo.yaml \
    prometheus/metrics_token \
    redis/redis.conf

  compose pull
  compose run --rm -T --no-deps otel-collector validate --config=/etc/otelcol/config.yaml < /dev/null
}

# Stop writers first so the dump matches the state the migrations start from.
backup_database() {
  compose up -d --no-deps --no-recreate --wait --wait-timeout 120 postgres redis
  compose stop caddy api celery-beat celery-worker

  mkdir -p "$backup_dir"
  local backup_file
  backup_file="$backup_dir/$(date -u +%Y%m%dT%H%M%SZ)-$IMAGE_TAG.dump"
  compose exec -T postgres sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' < /dev/null > "$backup_file.partial"
  mv -- "$backup_file.partial" "$backup_file"
  echo "Database backup: $backup_file"
}

restart_infrastructure() {
  compose stop
  local infrastructure
  mapfile -t infrastructure < <(
    compose config --services |
    awk '$0 != "api" && $0 != "caddy" && $0 != "celery-worker" && $0 != "celery-beat"'
  )
  compose up -d --no-build --no-deps --force-recreate --wait --wait-timeout 180 "${infrastructure[@]}"

  compose run --rm -T --no-deps api uv run --no-sync python - <<'PY'
import time
import urllib.request

pending = {
    "collector": "http://otel-collector:13133/",
    "loki": "http://loki:3100/ready",
    "tempo": "http://tempo:3200/ready",
}
deadline = time.monotonic() + 120
while pending and time.monotonic() < deadline:
    for name, url in list(pending.items()):
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    print(f"{name}: ready", flush=True)
                    del pending[name]
        except (OSError, TimeoutError):
            pass
    if pending:
        time.sleep(2)
if pending:
    raise SystemExit("Not ready: " + ", ".join(pending))
PY
}

release_application() {
  compose run --rm -T --no-deps api uv run --no-sync alembic upgrade head < /dev/null
  compose up -d --no-build --no-deps --force-recreate --remove-orphans --wait --wait-timeout 180 api celery-worker celery-beat caddy

  compose exec -T celery-worker uv run --no-sync celery -A app.celery.celery_app:celery_app inspect ping --timeout=10
}

# Logs tagged with the new version prove the release runs and telemetry reaches Loki.
verify_telemetry() {
  compose run --rm -T --no-deps api uv run --no-sync python - "$IMAGE_TAG" <<'PY'
import json
import sys
import time
import urllib.parse
import urllib.request

pending = {"etch-api", "etch-worker", "etch-beat"}
deadline = time.monotonic() + 90
while pending and time.monotonic() < deadline:
    for name in sorted(pending):
        query = '{service_name="' + name + '"} | service_version="' + sys.argv[1] + '"'
        params = urllib.parse.urlencode({"query": query, "since": "2m", "limit": 1})
        try:
            with urllib.request.urlopen("http://loki:3100/loki/api/v1/query_range?" + params, timeout=3) as response:
                result = json.load(response)
            if result.get("status") == "success" and result["data"]["result"]:
                print(f"{name}: logs reached Loki", flush=True)
                pending.remove(name)
        except (OSError, ValueError):
            pass
    if pending:
        time.sleep(2)
if pending:
    raise SystemExit("Logs missing in Loki: " + ", ".join(sorted(pending)))
PY
}

record_release() {
  if grep -q '^IMAGE_TAG=' .env; then
    sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$IMAGE_TAG/" .env
  else
    printf '\nIMAGE_TAG=%s\n' "$IMAGE_TAG" >> .env
  fi
}

# Free disk after a successful deployment: keep this and the previous release for rollback.
cleanup_old_releases() {
  local previous_tag=$1 image
  while IFS= read -r image; do
    case "$image" in
      *":$IMAGE_TAG" | *":${previous_tag:-$IMAGE_TAG}" | *":<none>") continue ;;
    esac
    # Images still used by a container are refused and stay in place.
    docker image rm "$image" || true
  done < <(
    docker image ls --format '{{.Repository}}:{{.Tag}}' \
      --filter reference=ghcr.io/vaakesh/etch-backend \
      --filter reference=ghcr.io/vaakesh/etch-frontend
  )
  docker image prune -f
  docker builder prune -f

  # Backup names start with a UTC timestamp, so the newest ten sort first.
  find "$backup_dir" -maxdepth 1 -type f -name '*.dump' | sort -r | tail -n +11 | xargs -r rm -f --
}

main() {
  exec 8> "$HOME/.etch-compose.lock"
  flock -w 600 8
  trap on_error ERR

  # Read before record_release overwrites it; cleanup keeps this release for rollback.
  local previous_tag
  previous_tag="$(sed -n 's/^IMAGE_TAG=//p' .env 2>/dev/null | tail -n 1 || true)"

  preflight
  backup_database
  restart_infrastructure
  release_application
  verify_telemetry
  record_release
  cleanup_old_releases "$previous_tag" || echo "Cleanup failed; the deployment itself succeeded." >&2
  compose ps
  echo "Deployment completed: $IMAGE_TAG"
}

main "$@"
