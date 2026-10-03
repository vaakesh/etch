# Etch frontend

React 19 + TypeScript + Vite frontend с cookie-only auth и защищённой dashboard-страницей `/`, которая загружает данные из `GET /bff/home`.

Перед изменениями прочитай `AGENTS.md`.

## Требования

- Node.js 24;
- npm из поставки Node.js.

Dockerfile использует Node 24.

## Локальный запуск

Команды выполняются из каталога `frontend/`:

```bash
npm ci
cp .env.example .env
VITE_PROXY_TARGET=http://localhost:8000 npm run dev
```

`frontend/.env` обязателен для frontend в dev и test Compose и используется при сборке prod. Если файла нет, `setup.py` создаёт его из `.env.example`. Значения:

- `VITE_API_URL` — frontend base URL API; по умолчанию `/api`;
- `VITE_PROXY_TARGET` — backend target для Vite dev proxy.

Dev proxy включается только при заданном `VITE_PROXY_TARGET`, принимает `/api/*` и удаляет `/api` перед отправкой запроса в backend. Шаблон `.env.example` задаёт target `http://api:8000` для Docker-сети. При запуске Vite напрямую на компьютере команда выше переопределяет target на `http://localhost:8000`.

В dev Compose исходники, `public`, `index.html`, package-файлы и конфигурации инструментов монтируются отдельно. Изменения исходников доступны без пересборки. `node_modules` используется из образа; после изменения зависимостей выполни `make rebuild` из корня проекта. Переменные из `frontend/.env` передаются через Compose без переопределения в `environment`; после изменения значений пересоздай frontend командой `make up`.

Абсолютный `VITE_API_URL` обходит dev proxy. Vite proxy не является production reverse proxy.

В `docker-compose-prod.yml` сервис `caddy` использует `Dockerfile.prod`: Node 24 собирает приложение с `VITE_API_URL` из `frontend/.env`, затем Caddy отдаёт готовый `dist` и проксирует `/api/*` в `api:8000`, удаляя `/api`. После изменения `frontend/.env` пересобери prod-образ. Node и Vite в runtime не запускаются. Caddy публикует порты 80 и 443, автоматически получает и обновляет HTTPS-сертификаты. Домен и разрешённый внешний IP задаются через обязательные `site_domain_prod` и `allowed_ip_prod` в корневом `.env`. Правила находятся в `Caddyfile`, инструкции для VPS — в [PRODUCTION.md](../PRODUCTION.md).

## Проверки

```bash
npm run format:check
npm run typecheck
npm run lint
npm run test
npm run build
```

Vitest сейчас работает в `node` environment. DOM test stack не настроен.

## Основные каталоги

- `src/api` — общий transport и глобальные API-типы;
- `src/auth` — централизованная cookie-only auth-инфраструктура;
- `src/app/router` — единственный корневой router и конфигурация маршрутов;
- `src/features/home` — контракт, API-запрос и состояние главной страницы;
- `src/pages` — route-level страницы;
- `src/styles` — глобальные стили.
