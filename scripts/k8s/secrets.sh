#!/usr/bin/env bash
set -Eeuo pipefail

# etch/
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$project_dir"

# контекст kubectl кластера, в котором создаются секреты
context="${1:?использование: secrets.sh <context>}"
namespace=etch

k() {
  kubectl --context "$context" "$@"
}

# существуют ли файлы
test -f .env
test -f backend/.env
test -f redis/users.acl
test -f backend/certs/jwt-private.pem
test -f backend/certs/jwt-public.pem

# создает секреты, обновляет существующие
apply_secret() {
  kubectl -n "$namespace" create secret generic "$@" --dry-run=client -o yaml | k apply -f -
}

kubectl create namespace "$namespace" --dry-run=client -o yaml | k apply -f -

# секреты целиком: нужные ключи манифесты берут сами через secretKeyRef
apply_secret etch-root-env --from-env-file=.env
apply_secret etch-backend-env --from-env-file=backend/.env
apply_secret etch-jwt-keys --from-file=backend/certs
apply_secret redis-acl --from-file=redis/users.acl

# доступ к приватным образам в ghcr.io; нужен только оверлею prod
if [[ -f .githubtoken.packages ]]; then
  kubectl -n "$namespace" create secret docker-registry ghcr-pull \
    --docker-server=ghcr.io \
    --docker-username=vaakesh \
    --docker-password="$(< .githubtoken.packages)" \
    --dry-run=client -o yaml | k apply -f -
fi
