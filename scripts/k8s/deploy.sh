#!/usr/bin/env bash
set -Eeuo pipefail

# шаги: образы (только local) -> секреты -> манифесты -> ожидание баз -> миграции -> рестарт приложения

# etch/
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_dir"

# local - образы :local и https://localhost, prod - образы из ghcr.io и настоящий домен
overlay_name="${K8S_OVERLAY:-local}"
overlay="k8s/overlays/$overlay_name"
namespace=etch

# получение значений из etch/.env
env_value() {
  sed -n "s/^$1=//p" .env | tail -n 1
}

site_domain=localhost
image_tag=local
cert_issuer=selfsigned
# попадает в метки логов и трейсов
environment=local

if [[ "$overlay_name" == prod ]]; then
  site_domain="$(env_value site_domain_prod)"
  # тег из окружения, как в scripts/deploy-prod.sh, иначе из .env
  image_tag="${IMAGE_TAG:-$(env_value IMAGE_TAG)}"
  # letsencrypt-staging - для первого запуска на новом сервере
  cert_issuer="${K8S_CERT_ISSUER:-letsencrypt}"
  environment=production

  if [[ -z "$site_domain" ]]; then
    echo "в .env не задан site_domain_prod" >&2
    exit 1
  fi
  if [[ ! "$image_tag" =~ ^[0-9a-f]{40}$ ]]; then
    echo "IMAGE_TAG должен быть полным sha коммита" >&2
    exit 1
  fi
fi

# собирает манифесты и подставляет значения вместо заглушек;
# LoadRestrictionsNone разрешает читать общие с docker compose конфиги вне k8s/
render() {
  kubectl kustomize --load-restrictor LoadRestrictionsNone "$1" | sed \
    -e "s/site-domain\.placeholder/$site_domain/g" \
    -e "s/image-tag-placeholder/$image_tag/g" \
    -e "s/cert-issuer-placeholder/$cert_issuer/g" \
    -e "s/environment-placeholder/$environment/g"
}

# только сборка манифестов, без обращения к кластеру
if [[ "${1:-}" == render ]]; then
  render "$overlay"
  exit 0
fi

# контекст kubectl кластера: kind-etch или контекст сервера
context="${K8S_CONTEXT:?задай K8S_CONTEXT - контекст kubectl кластера, например kind-etch}"

# все обращения к кластеру идут с явным контекстом, текущий контекст kubectl не меняется
k() {
  kubectl --context "$context" "$@"
}

rollout() {
  k -n "$namespace" rollout "$@"
}

if [[ "$overlay_name" == local ]]; then
  if [[ "$context" != kind-* ]]; then
    echo "оверлей local работает только в кластере kind, а не в $context" >&2
    exit 1
  fi

  docker build -f backend/Dockerfile.prod -t etch-backend:local backend
  docker build -f frontend/Dockerfile.prod -t etch-frontend:local frontend

  # образы собраны локально и в реестр не отправляются, поэтому кладутся прямо на ноды
  kind load docker-image etch-backend:local etch-frontend:local --name "${context#kind-}"
fi

bash scripts/k8s/secrets.sh "$context"
render "$overlay" | k apply -f -

for stateful in postgres redis rabbitmq tempo loki prometheus; do
  rollout status "statefulset/$stateful" --timeout=5m
done

# job неизменяем, поэтому пересоздается
k -n "$namespace" delete job migrate --ignore-not-found
render "$overlay/migrate" | k apply -f -
k -n "$namespace" wait --for=condition=complete job/migrate --timeout=3m

# рестарт подхватывает новый образ :local (тег не меняется) и измененные секреты:
# у секретов нет хеша в имени, сами поды на их изменение не реагируют
apps=(deployment/api deployment/celery-worker deployment/celery-beat deployment/frontend)
rollout restart "${apps[@]}"
for app in "${apps[@]}"; do
  rollout status "$app" --timeout=5m
done

echo "готово: https://$site_domain"
