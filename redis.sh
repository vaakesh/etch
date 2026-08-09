#!/usr/bin/env sh

set -eu
# -e - завершить скрипт, если команда закончилась с ошибкой
# -u - завершить скрипт при обращении к необъявленной переменной

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)" # абсолютный путь к директории файла


set -a
. "$SCRIPT_DIR/.env"
set +a

exec docker compose \
    -f "$SCRIPT_DIR/docker-compose.yml" \
    exec \
    -e REDISCLI_AUTH="$redis_password" \
    redis \
    redis-cli --user "$redis_user"