#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
export IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse HEAD)}"
if [[ ! "$IMAGE_TAG" =~ ^[0-9a-f]{40}$ ]]; then
  echo "IMAGE_TAG must be a full Git commit SHA." >&2
  exit 1
fi

exec 8> "$HOME/.etch-compose.lock"
flock -w 600 8

compose() {
  docker compose -f docker-compose-prod.yml -f docker-compose-prod-observability.yml "$@"
}

on_error() {
  local status=$?
  trap - ERR
  echo "Deployment failed: $IMAGE_TAG" >&2
  compose ps -a || true
  compose logs --no-color --tail=40 || true
  exit "$status"
}
trap on_error ERR

compose config --quiet
test -d backend/certs
test -f prometheus/metrics_token
test -f observability/otel-collector-prod.yaml
compose pull

compose up -d --no-deps --no-recreate --wait --wait-timeout 120 postgres redis
compose stop caddy api celery-beat celery-worker

backup_dir="$HOME/etch-backups"
mkdir -p "$backup_dir"
backup_file="$backup_dir/$(date -u +%Y%m%dT%H%M%SZ)-$IMAGE_TAG.dump"
compose exec -T postgres sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' < /dev/null > "$backup_file.partial"
mv -- "$backup_file.partial" "$backup_file"
echo "Database backup: $backup_file"

compose stop
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
    "prometheus": "http://prometheus:9090/-/ready",
    "grafana": "http://grafana:3000/api/health",
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

compose run --rm -T --no-deps api uv run --no-sync alembic upgrade head < /dev/null
compose up -d --no-build --no-deps --force-recreate --remove-orphans --wait --wait-timeout 180 api celery-worker celery-beat caddy

compose exec -T celery-worker uv run --no-sync celery -A app.celery.celery_app:celery_app inspect ping --timeout=10

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

if grep -q '^IMAGE_TAG=' .env; then
  sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$IMAGE_TAG/" .env
else
  printf '\nIMAGE_TAG=%s\n' "$IMAGE_TAG" >> .env
fi
compose ps
echo "Deployment completed: $IMAGE_TAG"
