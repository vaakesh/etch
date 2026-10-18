#!/usr/bin/env bash
set -Eeuo pipefail

# etch/
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_dir"

cluster=etch

for tool in docker kind kubectl helm; do
  command -v "$tool" >/dev/null || { echo "не найден $tool" >&2; exit 1; }
done

# существующий кластер не пересоздается; образ ноды зафиксирован в k8s/kind-cluster.yaml
if ! kind get clusters | grep -qx "$cluster"; then
  kind create cluster --name "$cluster" --config k8s/kind-cluster.yaml
fi

# ноды kind - контейнеры: после docker stop или перезагрузки кластер есть, но не запущен
kind get nodes --name "$cluster" | xargs docker start >/dev/null
until kubectl --context "kind-$cluster" get --raw /readyz >/dev/null 2>&1; do
  sleep 2
done
kubectl --context "kind-$cluster" wait --for=condition=Ready node --all --timeout=3m

bash scripts/k8s/addons.sh "kind-$cluster" kind
