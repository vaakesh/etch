#!/usr/bin/env bash
set -Eeuo pipefail

# etch/
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_dir"

# контекст kubectl кластера, в который ставятся аддоны
context="${1:?использование: addons.sh <context> <kind|k3s>}"
# kind - локальный кластер, k3s - сервер; metrics-server в k3s встроенный
mode="${2:?использование: addons.sh <context> <kind|k3s>}"

case "$mode" in
  kind | k3s) ;;
  *)
    echo "неизвестный режим $mode: нужен kind или k3s" >&2
    exit 1
    ;;
esac

traefik_values=(-f k8s/cluster/traefik-values.yaml)
if [[ "$mode" == kind ]]; then
  traefik_values+=(-f k8s/cluster/traefik-values-kind.yaml)
fi

# версии зафиксированы и одинаковы для всех кластеров
gateway_api_version=v1.6.3
traefik_chart_version=41.7.1
cert_manager_version=v1.21.2
metrics_server_chart_version=3.14.0

# ставит чарт, обновляет уже установленный
helm_install() {
  helm --kube-context "$context" upgrade --install "$@" --wait --timeout 5m
}

kubectl --context "$context" apply --server-side \
  -f "https://github.com/kubernetes-sigs/gateway-api/releases/download/$gateway_api_version/standard-install.yaml"

helm_install traefik traefik \
  --repo https://traefik.github.io/charts \
  --version "$traefik_chart_version" \
  --namespace traefik --create-namespace \
  "${traefik_values[@]}"

helm_install cert-manager cert-manager \
  --repo https://charts.jetstack.io \
  --version "$cert_manager_version" \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true \
  --set config.apiVersion=controller.config.cert-manager.io/v1alpha1 \
  --set config.kind=ControllerConfiguration \
  --set config.enableGatewayAPI=true \
  --set resources.requests.cpu=10m,resources.requests.memory=64Mi,resources.limits.memory=256Mi \
  --set webhook.resources.requests.cpu=10m,webhook.resources.requests.memory=32Mi,webhook.resources.limits.memory=128Mi \
  --set cainjector.resources.requests.cpu=10m,cainjector.resources.requests.memory=64Mi,cainjector.resources.limits.memory=256Mi

# на сервере сертификаты выдает let's encrypt: его издатели лежат в оверлее prod
if [[ "$mode" == kind ]]; then
  kubectl --context "$context" apply -f k8s/cluster/cluster-issuer-selfsigned.yaml

  # в kind у kubelet самоподписанные сертификаты
  helm_install metrics-server metrics-server \
    --repo https://kubernetes-sigs.github.io/metrics-server \
    --version "$metrics_server_chart_version" \
    --namespace kube-system \
    --set 'args={--kubelet-insecure-tls}'
fi
