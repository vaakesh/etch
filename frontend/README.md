# Etch frontend

Минимальный React 19 + TypeScript + Vite frontend-каркас. UI-страницы пока намеренно не добавлены: список `src/app/router/route-config.ts` пуст, а `src/pages` является точкой расширения.

Перед изменениями прочитай `AGENTS.md`.

## Требования

- Node.js 20.19+ или 22.12+;
- npm из поставки Node.js.

Dockerfile использует Node 20.

## Локальный запуск

Команды выполняются из каталога `frontend/`:

```bash
npm ci
cp .env.example .env
npm run dev
```

`.env` нужен только для локального переопределения настроек. Значения:

- `VITE_API_URL` — frontend base URL API; по умолчанию `/api`;
- `VITE_PROXY_TARGET` — backend target для Vite dev proxy.

Dev proxy включается только при заданном `VITE_PROXY_TARGET`, принимает `/api/*` и удаляет `/api` перед отправкой запроса в backend. Docker Compose задаёт target `http://api:8000`; пример локальной конфигурации использует `http://localhost:8000`.

Абсолютный `VITE_API_URL` обходит dev proxy. Vite proxy не является production reverse proxy.

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
- `src/pages` — route-level страницы;
- `src/features` — создаётся вместе с первой предметной фичей;
- `src/styles` — глобальные стили.
