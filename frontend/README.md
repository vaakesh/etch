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

В dev Compose исходники, `public`, `index.html`, package-файлы и конфигурации инструментов монтируются отдельно. Изменения исходников доступны без пересборки. `node_modules` используется из образа; после изменения зависимостей выполни `make dev-rebuild` из корня проекта. Переменные из `frontend/.env` передаются через Compose без переопределения в `environment`; после изменения значений пересоздай frontend командой `make dev-up`.

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

Vitest работает в `node` environment и исключает `e2e/`. Браузерные тесты запускаются отдельно через Playwright.

## Основные каталоги

- `src/api` — общий transport и глобальные API-типы;
- `src/auth` — централизованная cookie-only auth-инфраструктура;
- `src/app/router` — единственный корневой router и конфигурация маршрутов;
- `src/features/home` — контракт, API-запрос и состояние главной страницы;
- `src/pages` — route-level страницы;
- `src/styles` — глобальные стили.

## Playwright

Перед написанием или изменением браузерных тестов обязательно прочитай [playwright_rules.md](playwright_rules.md). Реализованные сценарии и пробелы перечислены в [e2e/scenarios.md](e2e/scenarios.md).

Установить зависимости и браузеры (из `frontend/`):

```bash
npm ci
npm run test:e2e:install
```

На чистой Linux-машине/в CI установи также системные библиотеки: `npx playwright install --with-deps chromium firefox webkit`. В CI используй Node 24. Не обновляй Playwright отдельно от lock-файла и его браузеров.

```bash
npm run typecheck:e2e
npm run test:e2e
npm run test:e2e:mocked
npm run test:e2e:ui
npm run test:e2e:report
```

`test:e2e` — весь mocked-набор в Chromium (сейчас smoke, вход, регистрация и выход). `test:e2e:mocked` — Chromium/Firefox/WebKit desktop, Android/iPhone и iPad emulation; дополнительные projects выбирают `@smoke`/`@responsive`. Основной Chromium запускает весь mocked-набор. Примеры целевого запуска:

```bash
npm run test:e2e -- e2e/mocked/auth.spec.ts --repeat-each=3 --retries=0
npm run test:e2e:mocked -- --project=mocked-ios
npm run test:e2e:mocked -- --list
```

Mocked и visual сами запускают отдельный Vite на `http://127.0.0.1:4187` с `--strictPort`; можно задать `PLAYWRIGHT_PORT=4188`. Занятый порт вызывает ошибку: чужой сервер не переиспользуется. API URL зафиксирован как `/api`, proxy target — недоступный локальный порт: тесты обслуживает только mock router, backend не нужен. Все API-запросы должны иметь handler; неизвестные API и внешние HTTP-запросы проваливают тест.

Структура: `e2e/mocked`, `e2e/integration`, `e2e/visual`; specs импортируют `test`/`expect` из соответствующего `e2e/fixtures/*-test.ts`. `currentUser` — option моковой fixture, по умолчанию гость; `test.use({ currentUser: buildCurrentUser() })` включает bootstrap авторизованного пользователя. Предметные ответы задавай через `api.on(method, backendPath, handler)` до `page.goto`. Handler получает `route`, `request`, `url`; query и body проверяются в самом сценарии. Повторная регистрация method/path заменяет handler для отрицательных/изменяемых состояний. Login/logout не подменяются автоматически: сценарий должен явно задать их поведение через fixture `auth` — `auth.allowLogin(credentials, user)`, `auth.allowRegistration(user)`, `auth.allowLogout()`; после них `GET /users/me` отвечает по новому состоянию сессии. Для pending-состояний используй `api.gate()`: handler ждёт `gate.opened`, тест вызывает `gate.open()`.

Fixtures собирают необработанные ошибки браузера, console errors и network failures. Ожидаемый HTTP error укажи через `diagnostics.expectHttpError({ method, pathname: '/api/...', status, reason })`; разрешается только сообщение загрузки ресурса, соответствующее такому реальному ответу. Намеренный сетевой сбой (`route.abort`) разреши через `diagnostics.expectRequestFailure({ method, pathname: '/api/...', reason })`. JS-ошибки этим не скрываются. Cookies, local storage, страницы и mock state изолированы по тесту.

### Integration

Основной способ — из корня проекта:

```bash
make test-e2e
make test-down
```

`make test-e2e` выполняет `typecheck:e2e`, mocked и visual, затем удаляет прежний test Compose вместе с volumes, поднимает чистый стенд с миграциями и запускает integration. Если наборы без backend упали, стенд не поднимается. После прогона стенд остаётся для разбора логов и базы; `make test-down` удаляет его вручную. `make test-api` (backend pytest) использует тот же стенд и тоже начинает с его удаления. `make test-frontend` выполняет format, typecheck, lint, Vitest и build без Docker. `make test-all` последовательно выполняет `make test-frontend`, `make test-e2e` и `make test-api`.

Ручной запуск на уже поднятом стенде:

```bash
PLAYWRIGHT_INTEGRATION_BASE_URL=http://localhost:YOUR_TEST_FRONTEND_PORT npm run test:e2e:integration
```

Вместо `YOUR_TEST_FRONTEND_PORT` подставь фактический `frontend_port_test` из корневой конфигурации. Команда требует явный origin выделенного test frontend; без него завершится ошибкой. Она не поднимает сервер, не делает migrations/seed и не очищает БД. Стенд запускай из корня по [инструкции](playwright_rules.md#4-запуск-и-ограничения-тестового-стенда). Не используй production/dev URL. Нельзя параллельно запускать backend integration pytest, очищающий те же таблицы.

Первый integration smoke `ENV-001` проверяет `/api/ready` через frontend proxy, настоящий гостевой `401 /users/me` и отображение login. API не перехватывается. PostgreSQL и Redis должны быть готовы. readiness не подтверждает миграции и вход пользователя.

`INT-001` (вход → reload → выход) и `INT-002` (регистрация в UI) работают с настоящими cookies в Chromium. Аккаунты выдаёт fixture `accounts`: `await accounts.create()` — готовый уникальный аккаунт через API, `accounts.reserve()` — данные для регистрации через UI; после теста аккаунты удаляются через `DELETE /api/users/me`.

Перед каждым integration-тестом и после него fixture очищает Redis test-стенда (`docker compose -f docker-compose-test.yml exec api …`), поэтому лимиты регистрации и входа не мешают повторным прогонам. Для этого стенд должен быть поднят локально из `docker-compose-test.yml` репозитория, а `docker` — доступен процессу тестов; скрипт отказывается работать с базой, отличной от `etch_test_integration`. WebKit для authenticated-цепочек и INT-003…010 — следующий этап.

Шрифты во всех наборах обслуживаются из закреплённых devDependencies `@fontsource-variable/inter` и `@fontsource-variable/playfair-display` (OFL-1.1). Fixture заменяет только Google Fonts stylesheet/font resources; код приложения не меняется. Это исключает внешнюю сеть и стабилизирует шрифты, но не проверяет доступность Google Fonts в production.

### Visual и артефакты

```bash
npm run test:e2e:visual
```

Baseline для формы входа хранится в `e2e/visual/__screenshots__/` отдельно для desktop/mobile. Сравнивай на Linux с браузером из закреплённого Playwright и одинаковыми шрифтами. Первый baseline или намеренное изменение: запусти целевой spec с `--update-snapshots`, просмотри изображения и diff, затем повтори обычное сравнение. Не обновляй baselines автоматически в CI.

Trace, screenshot/video на падении и JUnit находятся в `test-results/`, HTML — в `playwright-report/`; каталоги исключены из Git, Docker context и formatter/linter. Последний запуск перезаписывает HTML, а результаты трёх наборов разделены. В CI включены `forbidOnly`, один retry и ошибка на flaky; локально retries=0. Реальные CI jobs для Playwright пока не подключены.

Настройки suite передаются npm scripts через `PLAYWRIGHT_SUITE` (POSIX shell, как окружение проекта). Выбор suite меняет discovery целиком, поэтому integration/visual не попадут в обычный mocked-запуск, а Playwright — в Vitest.
