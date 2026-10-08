# Правила Playwright для Etch

Документ для агента, который внедряет и расширяет браузерные тесты frontend. Прочитай его перед задачей вместе с корневым `AGENTS.md` и `frontend/AGENTS.md`. Перед изменением backend или инфраструктуры отдельно прочитай применимые инструкции. Не трогай посторонний working-tree diff.

## 1. Статус и границы

Первый этап среды внедрён: `@playwright/test`, отдельный TS config, три набора projects (mocked/integration/visual), строгий API router, fixtures, локальные тестовые шрифты, стартовые smoke и visual case. Команды и фактическое покрытие перечислены в [README.md](README.md) и [e2e/scenarios.md](e2e/scenarios.md).

Дальнейшие разделы задают целевое покрытие. Полные пользовательские цепочки, integration seed и CI gates ещё не реализованы. ENV-001 проверяет доступность реального стенда без создания данных; он не заменяет authenticated integration-тесты. Vitest сохраняет Node environment, Playwright запускается отдельно.

Цель: покрыть основные пользовательские действия и состояния всех существующих страниц, адаптивность и критические связи с backend. Покрытие измеряй по сценариям и рискам, а не числом тестов или количеством скриншотов. Не обещай проверку «всех устройств» по эмуляции нескольких размеров.

Источники истины:

1. Маршруты: `frontend/src/app/router/route-config.ts`; поведение: соответствующие страницы, feature hooks, auth и shell.
2. API: `backend/app/{auth,users,cards,decks,training_sessions,bff}/{router,schemas}.py`, общие схемы, error handlers и ограничения. OpenAPI используй как перекрёстную проверку.
3. Стенд: `docker-compose-test.yml`, `Makefile`, `setup.py`, Dockerfile, `.env.example`, `.github/workflows/pipeline.yml`.
4. Существующие frontend/backend-тесты помогают понять поведение, но не заменяют действующий контракт.

Перечитывай относящиеся к сценарию источники: снимок состояния в этом документе может устареть. Не добавляй тесты отсутствующих возможностей, например отдельной страницы регистрации, сброса пароля или UI перестановки карточек только потому, что существует backend endpoint.

## 2. Три набора тестов

| Набор         | Что проверяет                                                                                                | Окружение                                                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| `mocked`      | Основное покрытие поведения: формы, переходы, права в UI, ошибки, loading, пагинация, гонки, адаптивность    | Настоящее приложение в браузере; все API-запросы приложения подменены         |
| `integration` | Небольшое число критических цепочек: cookies, proxy, сохранение данных, права между пользователями, практика | Настоящие frontend, API, PostgreSQL, Redis; без подмены API приложения        |
| `visual`      | Стабильные состояния ключевых страниц и диалогов                                                             | Моковые данные; фиксированные браузер, ОС, шрифты, тема, язык, время и размер |

Начинай с mocked. Integration добавляй там, где важен реальный контракт или состояние сервера. Visual дополняет функциональные assertions. Не переноси в браузер все варианты чистых парсеров и алгоритмов, уже покрытые Vitest.

Частичная подмена API при настоящем backend не считается integration. Если она нужна для отдельной диагностики, явно назови тест гибридным и не включай его в отчёт о сквозном покрытии.

## 3. Единая структура и команды

Создавай файлы по мере появления ответственности, без пустых заготовок:

```text
frontend/
  playwright.config.ts
  tsconfig.playwright.json
  e2e/
    scenarios.md
    fixtures/
      mocked-test.ts
      integration-test.ts
      visual-test.ts
    mocks/
      api-router.ts
      auth.ts
      library.ts
      practice.ts
    data/
      builders.ts
      imports/
    helpers/
      dialogs.ts
      layout.ts
    integration-support/
      seed.ts
      cleanup.ts
    mocked/
      auth.spec.ts
      library-decks.spec.ts
      practice.spec.ts
    integration/
      auth.spec.ts
      learning-flow.spec.ts
    visual/
      library.spec.ts
      practice.spec.ts
```

- Язык — TypeScript, runner — `@playwright/test`. Не вводи второй browser runner или отдельный mock server без необходимости: начни с `browserContext.route`.
- Каждый spec импортирует `test` и `expect` из fixture своего набора. Общие проверки ошибок и изоляции подключаются автоматически через fixture. Integration fixture не наследует моковую авторизацию.
- Предметные mock handlers разделяй по фичам. Не создавай один handler на сотни условных веток в каждом spec. Builders возвращают новые данные на каждый вызов.
- Helpers выноси для повторяющегося осмысленного действия. Page Object нужен, только если устраняет повторение; не делай обёртки над каждым `click` и универсальный `BasePage`.
- `testDir` — `./e2e`; `testMatch`/projects однозначно разделяют три набора. Visual specs не должны автоматически попадать в mocked-проекты.
- Исключи `e2e/**` из Vitest, сохранив его стандартные excludes: сейчас Vitest может обнаружить новые `*.spec.ts`. Не ломай `src/**/*.test.*`.
- Playwright исполняет TS, но не заменяет typecheck. Включи config, specs и helpers в отдельный строгий tsconfig и отдельную npm-проверку. Учитывай Node globals в ESLint для конфигурации и test support.
- Добавь в ignores `playwright-report/`, `test-results/`, временные auth state, секреты и сгенерированные данные. Baseline PNG храни в Git; actual/diff/trace/video — артефакты запуска.
- Зафиксируй зависимость lock-файлом. Версия Playwright Docker image, если он используется, должна совпадать с пакетом.

Контракт npm scripts (актуальная реализация — в `package.json`):

| Script                 | Назначение                                                       |
| ---------------------- | ---------------------------------------------------------------- |
| `test:e2e`             | Только mocked, основной Chromium desktop                         |
| `test:e2e:mocked`      | Вся назначенная mocked-матрица                                   |
| `test:e2e:integration` | Только integration, проверяет явно заданный URL тестового стенда |
| `test:e2e:visual`      | Только visual, сравнение с утверждёнными baselines               |
| `test:e2e:ui`          | Интерактивная отладка mocked                                     |
| `test:e2e:report`      | Открытие HTML-отчёта                                             |
| `typecheck:e2e`        | Проверка TS конфигурации и тестов                                |

Все npm-команды выполняй из `frontend/`. В README укажи реальные соответствия scripts и projects. Не делай так, чтобы обычный `npm run test` внезапно требовал Docker и браузеры.

## 4. Запуск и ограничения тестового стенда

### Mocked и visual

Поднимай отдельный Vite через Playwright `webServer`, с фиксированным свободным портом и `--strictPort`. Явно задай `VITE_API_URL=/api`, чтобы локальный `.env` не отправил запросы на другой сервер. Укажи `baseURL`, host и порт согласованно. Backend для этих наборов не требуется.

В CI `reuseExistingServer: false`. Локальное переиспользование допускается только при подтверждённой конфигурации; чужой сервер на том же порту не должен делать тест зелёным. Дождись доступности приложения и затем его ожидаемого UI-состояния.

### Integration

В `docker-compose-test.yml` действительно есть `api`, `frontend`, `postgres`, `redis`. Frontend — Vite dev server из Docker image. Исходники frontend не примонтированы: после изменения UI или зависимостей требуется пересборка. Это проверка dev proxy, не production Caddy или production bundle.

Основной способ — из корня проекта:

```bash
make test-e2e   # typecheck:e2e, mocked, visual, затем чистый стенд и integration
make test-down  # удалить стенд и его volumes вручную
```

`make test-e2e` сначала выполняет наборы без backend; при их падении стенд не поднимается. Перед подъёмом стенд и его volumes удаляются (`down --volumes`), миграции применяются с нуля. После прогона стенд не удаляется, чтобы можно было изучить логи и базу; его сносит `make test-down` или предочистка следующего `make test-e2e`/`make test-api`.

Те же шаги вручную, для отладки на уже поднятом стенде:

```bash
uv run --no-project python setup.py check test
docker compose -f docker-compose-test.yml build api frontend
docker compose -f docker-compose-test.yml up -d --wait --wait-timeout 120 postgres redis
docker compose -f docker-compose-test.yml run --rm -T --no-deps api uv run --no-sync alembic upgrade head
docker compose -f docker-compose-test.yml up -d --wait --wait-timeout 180 api frontend
```

Затем запустить integration из `frontend/`. Playwright integration не запускает Compose автоматически: подготовь стенд этими командами, затем передай его origin в npm script.

Обязательные условия:

- `setup.py` может потребовать конфиги и JWT-ключи. CI должен готовить их заранее по существующему pipeline; не рассчитывай на интерактивные ответы.
- URL бери из фактического `frontend_port_test`, передавай в `PLAYWRIGHT_INTEGRATION_BASE_URL`. Не подставляй dev/prod URL по умолчанию. Для API setup используй тот же origin и `/api` либо явно документированный отдельный API URL.
- В Docker-сети proxy target — `http://api:8000`, браузер на хосте использует опубликованный frontend-порт. При runner в контейнере `localhost` означает контейнер runner. Не путай эти адреса.
- Проверяй `VITE_API_URL` и `VITE_PROXY_TARGET`: абсолютный API URL обходит Vite proxy. Через same-origin `/api` проще проверить реальную cookie-сессию и избежать случайных CORS-различий.
- `/ready` подтверждает доступность PostgreSQL и Redis, но не выполнение миграций или seed. Перед тестами отдельно проверь миграции, frontend HTTP, proxy и authenticated `GET /users/me`.
- `make test-api` запускает backend pytest и не запускает Playwright; `make test-e2e` не запускает backend pytest; `make test-frontend` выполняет format, typecheck, lint, Vitest и build без Docker; `make test-all` выполняет их последовательно: `test-frontend`, `test-e2e`, `test-api`. `test-e2e` и `test-api` используют один стенд `etch-test` и перед запуском удаляют его вместе с volumes, поэтому следующий запуск стирает базу и логи предыдущего. Backend integration fixtures делают `TRUNCATE`: не запускай их одновременно с E2E на одной базе. Раздели jobs/стенды или выполняй последовательно с повторным seed.
- Compose использует persistent volumes и фиксированные published ports. Другой project name изолирует обычные volumes, но не устраняет коллизии портов и внешних подключений: проверь DSN, Redis и ports для каждого параллельного job.
- Не выполняй `down --volumes`, `TRUNCATE`, Redis flush или массовую очистку в общей/dev базе. Cleanup допустим только для явно выделенного одноразового стенда либо созданных этим запуском сущностей. Не выводи полные `.env` и `docker compose config` с секретами в отчёт.

### Cookies, аккаунты и rate limits

Backend `auth/cookies.py` выставляет `HttpOnly`, `Secure`, `SameSite=lax`. Тестовый frontend обслуживается по HTTP. До расширения integration проверь настоящий login → `/users/me` → reload в каждом выбранном браузере. Поведение Secure cookies на localhost не считай гарантией для произвольного hostname, IP или контейнерного адреса. Если браузер не принимает/не отправляет cookies, настрой HTTPS у тестового входа. Не ослабляй production cookies и не скрывай проблему ручной установкой cookies. `ignoreHTTPSErrors` сам по себе не превращает HTTP в HTTPS.

Реальные токены получать только штатным login. Не генерировать JWT, не записывать access/refresh в localStorage, не передавать ручной Authorization header. API login через `context.request` может подготовить cookie jar этого browser context; отдельный `request.newContext` потребует явного переноса storage state и проверки origin. Повторное использование state допустимо только с учётом серверных мутаций и ротации refresh. См. [Playwright: authentication](https://playwright.dev/docs/auth).

Обнаруженные ограничения: регистрация — 5 запросов/час на IP, login — 10/минуту на IP (`backend/app/redis/rate_limiters.py`). Новое имя пользователя не обходит IP-лимит; за proxy несколько workers могут выглядеть одним клиентом. Не регистрируй пользователя через публичный endpoint перед каждым тестом.

Для основного integration-набора подготовь ограниченный пул независимых пользователей через отдельный test-only seed, использующий backend service layer и проверку test DB. Сейчас такого seed нет: вместо него integration fixture очищает Redis выделенного test-стенда перед каждым тестом и после него (`frontend/e2e/integration-support/redis.ts`), а аккаунты создаются публичной регистрацией через `accounts.create()` и удаляются после теста. Если seed понадобится, сначала изучи его зависимости, транзакции и реальные требования схем; не импортируй pytest fixture как готовую фабрику и не добавляй production endpoint «для тестов». Отдельный браузерный registration smoke оставь настоящим, с контролируемым бюджетом регистраций.

Первоначально integration выполняй с одним worker. Аккаунты разделяй по run/project/parallel worker; retries должны получать чистое состояние. Для logout, refresh, изменения настроек и проверок двух пользователей нужны независимые серверные сессии. Не используй один сохранённый refresh token одновременно во всех workers. Параллелизм увеличивай только после проверки rate limits и изоляции.

Seed создаёт только предпосылки, а проверяемая операция выполняется через UI. Например, для теста создания колоды нельзя заранее создавать эту же колоду API-запросом. После UI-мутации проверь reload/повторное чтение; для критической интеграции добавь независимый API read-back. Не используй чтение SQL как единственное доказательство результата в браузере.

Cleanup выполняй в teardown/finally, включая упавшие сценарии. Учитывай, что logout инвалидирует сессию, а удаление публичной колоды может создать архив: иногда нужен отдельный test-only cleanup. Ошибка cleanup должна быть видна, но не скрывать исходное падение.

## 5. Правила мокирования

Перехватывай сетевую границу приложения, сохраняя настоящий React, router, hooks и API client. Не подменяй `useAuth`, `apiFetch` или внутренний React state через browser evaluate. Установи routes до первого `goto`, для нескольких вкладок используй `context.route`. См. [Playwright: mock APIs](https://playwright.dev/docs/mock).

- Mock router сопоставляет origin, pathname, HTTP method и значимые query/body. Используй `URL`/`searchParams`, а не сравнение порядка query-строки. Сохраняй trailing slash: `POST /cards/` и `POST /decks/create` — разные реальные формы маршрутов.
- Отличай браузерный `/api/...` от backend-path без `/api`. Подменяй только настроенную API-границу, не статические файлы, Vite modules и SPA-навигацию.
- Неизвестный API-запрос должен прервать запрос, попасть в диагностический список и провалить тест при teardown. Не возвращай универсальное `{}` с 200 и не пропускай его на настоящий backend.
- Для mocked запрещены `route.fetch()` и passthrough к API. Доступ к внешним ресурсам ограничь явным списком; шрифты/ассеты должны быть воспроизводимыми.
- Задай `serviceWorkers: 'block'` в mocked/visual, чтобы service worker не обходил intercept. Это настройка harness, а не доказательство проверки offline/PWA поведения. См. [Playwright: network](https://playwright.dev/docs/network).
- В фикстурах используй реальные wire-поля (`snake_case`), nullable/optional, вложенные объекты, значения enums, статусы и пустые ответы. Не отдавай UI model с camelCase вместо backend response. Path IDs сверяй со схемами: многие маршруты требуют UUIDv7; для real-тестов бери ID сервера, для mocks используй валидные фиксированные UUIDv7.
- Builder по умолчанию создаёт валидный минимальный объект. Длинные строки, Unicode, границы размеров, чужой owner и повреждённый контракт — именованные варианты, которые выбирает сам тест. Не используй недетерминированный faker или `Math.random()` для ожидаемых данных.
- Сценарий задаёт только нужное состояние. Общие auth/bootstrap responses централизованы, но не должны незаметно включать все функции и успех всех мутаций.
- После успешной мутации mock обновляет состояние последующих GET, включая reload и BFF-представления. После неудачи данные остаются прежними. Это небольшая модель сценария, не копия backend business logic.
- Проверяй body/query значимой операции и UI-результат. Число запросов проверяй только там, где это контракт сценария: один submit, отсутствие запроса при невалидной форме, отсутствие бесконечного refresh. Не привязывай обычный GET к точному количеству из-за StrictMode, отмен и cache.
- Для loading и конкурирующих ответов используй управляемый deferred response: запрос получен → assert loading → разрешить ответ → assert результат. Порядок задавай по смыслу запроса, а не «третий fetch». Освобождай ожидания при teardown.
- HTTP error моделируй соответствующим status и настоящим error envelope из backend handlers. Сетевой сбой — `route.abort`, некорректный контракт — отдельный malformed response. Не смешивай их в один generic error.
- Пагинация различается: library/profile — cursor; catalog — page/limit и массив; deck/archive cards — offset/limit и массив; история items — ps/pn. Предусмотри полную страницу и следующий пустой ответ, чтобы поймать бесконечную дозагрузку.
- При изменении backend schema обновляй затронутые fixtures и integration-проверку. Не получай ожидаемое значение тем же frontend parser/formatter, который тестируешь: сравнивай с известными данными сценария.

Auth mock должен воспроизводить поток: bootstrap `GET /users/me`; login `POST /auth/login` → `GET /users/me`; logout с последующим unauthorized; `401` обычного запроса → refresh → не более одного повтора. Одновременные refresh объединяются внутри API client одной вкладки. Между вкладками не ожидай ровно один HTTP refresh; отдельно учитывай Web Locks и BroadcastChannel. `403` предметной операции не должен ошибочно превращаться в logout. Network/5xx при refresh и окончательный unauthorized — разные UI-состояния.

## 6. Матрица браузеров и экранов

Размеры ниже — начальная матрица в CSS pixels. Device descriptor задаёт также user agent, DPR, touch и mobile-поведение; одной смены viewport для touch-теста недостаточно. Выбери доступные descriptors установленной версии. WebKit desktop не равен реальному Safari на iPhone, а эмуляция не проверяет экранную клавиатуру и аппаратные особенности. См. [Playwright: emulation](https://playwright.dev/docs/emulation).

| Project                            | Настройки                                                   | Что запускать                                               |
| ---------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------- |
| `mocked-chromium`                  | Chromium, desktop 1440×900                                  | Все mocked-сценарии                                         |
| `mocked-firefox`                   | Firefox, desktop 1440×900                                   | `@smoke` и browser-sensitive сценарии                       |
| `mocked-webkit`                    | WebKit, desktop 1440×900                                    | `@smoke`, dialogs, focus, storage/navigation                |
| `mocked-android`                   | Chromium, например Pixel 7 descriptor                       | `@smoke` и `@responsive`, реальные touch-действия           |
| `mocked-ios`                       | WebKit, например iPhone 13 descriptor                       | `@smoke` и `@responsive`, touch/dialog/scroll               |
| `mocked-tablet`                    | WebKit, например iPad Mini descriptor                       | `@responsive`, touch-навигация и широкие диалоги            |
| `integration-chromium`             | Desktop, настоящий стенд                                    | Весь небольшой integration-набор                            |
| `integration-webkit`               | WebKit; descriptor iPhone при mobile smoke                  | Auth/reload и одна короткая практика после проверки cookies |
| `visual-desktop` / `visual-mobile` | Фиксированный Chromium desktop / Chromium mobile descriptor | Только назначенные visual cases                             |

Projects задают окружение и выбор тестов; не вставляй ветвление по browser name в каждый spec. Если возможности браузера различаются, укажи причину и отдельное ожидаемое поведение. См. [Playwright: projects](https://playwright.dev/docs/test-projects).

Дополнительные targeted viewport cases: 320×568, 360×640, 390×844, 768×1024, 1024×768, 1366×768, 1920×1080 и mobile landscape. Не размножай каждый CRUD-кейс на все размеры.

Проверяй границы именно затронутого CSS: для breakpoint B — B−1, B и B+1. В текущем UI есть shell 860/861, library/catalog 760/420, practice 700/440/340, settings 640, отдельные max-height условия. Перечитай CSS конкретной страницы: эти значения не универсальны. Responsive specs, самостоятельно меняющие viewport, ограничь нужными projects, чтобы не умножать одинаковую проверку.

Дополнительные оси: `ru-RU`/`en-US`, light/dark/system, reduced motion, короткий/длинный контент, пустая/полная страница. Основное поведение проверяй в одной фиксированной комбинации; остальные распределяй по рискам. Для каждой страницы нужен хотя бы обзор в обоих языках и темах, но полный декартов продукт не требуется. Browser locale не заменяет настройки пользователя: синхронизируй `/users/me.settings`, local preferences и `colorScheme` с целью теста.

### Что считать проверкой адаптивности

- Нет непредусмотренного горизонтального overflow страницы после загрузки, открытия диалога и ошибки. Проверяй `scrollWidth <= clientWidth + 1` через повторяющийся assertion; локальные прокручиваемые области разрешены явно.
- Важные кнопки доступны обычным click/tap после естественной прокрутки, не закрыты fixed header/footer и не требуют hover на touch. `toBeVisible` само по себе не доказывает отсутствие перекрытия.
- Списки, тексты карточек, длинные слова/URL, счётчики, локализованные подписи и сообщения об ошибке не выталкивают действия за экран. Проверяй разрешённый перенос/обрезку и доступ к полному тексту.
- Диалог помещается по ширине, его содержимое и footer достижимы при малой высоте. Фон не получает непреднамеренный scroll. После закрытия восстанавливаются focus и возможность прокрутки.
- Проверяй Tab/Shift+Tab, Enter/Space по роли контрола, Escape там, где закрытие разрешено, focus trap модального окна и возврат фокуса. В pending-состоянии закрытие может быть заблокировано — сверь реализацию и требования.
- После смены размера/ориентации не теряются введённые данные и активная практика. Не ограничивайся открытием страницы сразу с новым размером.
- Для reflow/увеличенного текста не используй DPR как замену browser zoom. Реальную мобильную клавиатуру, системный text scaling и физические устройства вынеси в отдельную ручную проверку с явной отметкой в отчёте.
- Если внедряется axe, закрепи версию `@axe-core/playwright` и проверяй стабильную страницу и открытый диалог. Автоматический scan дополняет клавиатурный сценарий; он не доказывает полную доступность. Новые нарушения исправляй или регистрируй, не отключай целые группы правил ради зелёного отчёта.

## 7. Реестр сценариев

Веди реестр `frontend/e2e/scenarios.md`. Одна строка — одна проверяемая история, со столбцами `ID | priority | mode | route | preconditions | action | observable result | projects/tags | spec | status/gap`. В начале все сценарии planned. Статусы: planned, implemented, blocked (с причиной), not-applicable (с обоснованием). Наличие spec ещё не означает успешный прогон: результат и дату запуска записывай в отчёт задачи.

ID стабильные: `AUTH-001`, `LIB-DECK-001`, `PRACTICE-001`, `INT-001`, `VIS-001`. Группы ниже нужно разложить на отдельные истории; не собирай всю строку таблицы в один длинный тест. P0 — вход, сохранение пользовательских данных, обучение; P1 — остальное основное поведение; P2 — редкие сочетания и диагностика. Это порядок реализации, а не разрешение навсегда пропустить P1/P2.

| Группа / маршруты                                  | Сценарии для mocked                                                                                                                                                                                                                                                                         | Приоритет |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| Auth `/login`, `?mode=register`                    | Вход; переключение регистрации; успешная регистрация и автоматический login; аккаунт создан, но login не удался; локальная валидация без запроса; неверные credentials; конфликт username/email; 422, сеть, 5xx; pending и повторный submit; очистка/сохранение полей по текущему поведению | P0        |
| Guard, shell, `*`                                  | Protected deep link без сессии; authenticated `/login`; bootstrap pending/error/retry; 404 для guest и authenticated; reload и Back/Forward; переходы навигации, активный раздел, desktop/touch shell; фактическая политика возврата после login                                            | P0        |
| Auth lifecycle                                     | Refresh success; окончательный 401; refresh 401/403 и network/5xx; параллельные 401; logout и очистка пользовательских caches; две вкладки одного context; смена пользователя без данных предыдущего                                                                                        | P0/P1     |
| Home `/`                                           | Заполненный dashboard; нулевые показатели и пустые колоды; loading/error/retry; корректные переходы в колоду и практику; длинные названия, даты и счётчики                                                                                                                                  | P1        |
| Library decks `/library`, `/library/decks`         | Создание private/public; обязательные поля/лимиты; empty/search/no results; cursor load-more и конец списка; избранное и снятие; full/compact представление и persistence; переходы; удаление с подтверждением/отменой и ошибкой; refresh списка после изменения                            | P0        |
| Library cards `/library/cards`                     | Создание, редактирование, удаление; поиск и cursor; пустые/длинные front/back; языки; добавление в одну/несколько колод; already-present, заполненная колода, частичный сбой назначений; сохранность формы и повтор после ошибки                                                            | P0        |
| Import dialog                                      | Валидный JSON, preview, submit, результат; пустой/сломанный JSON, неверный root/поля/язык; лимит числа карточек и вместимости колоды; исправление и повтор; серверный конфликт/ошибка; отсутствие двойного импорта. Полную математику Unicode/лимитов оставь unit-тестам                    | P0/P1     |
| Deck `/decks/:deck_uuid`                           | Своя/чужая, private/public, saved/unsaved; карточки offset/limit; пустая колода; edit/delete по правам; save/unsave/favourite там, где есть действия; запуск практики; invalid UUID, missing/forbidden resource                                                                             | P0/P1     |
| Editor `/library/:deck_uuid/edit`                  | Загрузка и изменение title/description/privacy; отмена и невалидные значения; редактирование карточки; удаление связи с колодой отдельно от удаления самой карточки; import; pending/error/retry; прямой вход без прав; отражение изменений в других представлениях                         | P0        |
| Catalog `/catalog`                                 | Поиск, смена запроса с опоздавшим старым ответом; page/limit, конец выдачи; preview и дозагрузка карточек; save/unsave и синхронизация библиотеки; переход в профиль/колоду/практику; права владельца; touch preview и закрытие                                                             | P1        |
| Archive `/library/decks/archive`                   | Нет предложений/есть предложения; детали и offset cards; сохранить архивную копию; already_preserved/copy_deleted по реальному контракту; переход к копии; недоступный архив, ошибка загрузки/сохранения; обновление после перехода публичной колоды в private или её удаления              | P1        |
| Profile `/users/:username`                         | Свой/чужой профиль; cursor списка колод, empty/error/retry; private visibility по viewer; неизвестный username; переходы; logout и его диалог; смена пользователя при открытой странице                                                                                                     | P1        |
| Practice setup `/practice?deck=...`                | Проверка доступности колоды; выбор стороны и числа слов; малый/пустой/недоступный deck; start/pending/error; корректный body и переход к session; невалидные/conflicting query по текущей политике                                                                                          | P0        |
| Practice active `/practice?session=...`            | Resume с прямой ссылки и reload; правильный/неправильный ответ, canonical answer, skip; Enter и touch; защита от двойного submit; ошибка ответа и повтор без потери ввода/прогресса; финальный результат и повторная тренировка                                                             | P0        |
| Practice lifecycle                                 | Pause/resume; activity resume/heartbeat/pause, tracker UUID и ошибки; уход/возврат; fullscreen и fallback по поддержке браузера; конфликт уже отвеченной/завершённой сессии; восстановление завершённого результата после reload                                                            | P1        |
| Practice list `/practice`                          | Все/completed/in_progress/abandoned; cursor, empty/error/retry; продолжить незавершённую; открыть историю; удалённая колода с nullable deck/title                                                                                                                                           | P1        |
| History `/practice/sessions/:session_uuid/history` | Правильные, неверные, пропущенные и неотвеченные items; порядок и поля; ps/pn дозагрузка; empty/error/forbidden/not found; доступные фильтры/переходы; длинные ответы и mobile rows                                                                                                         | P1        |
| Settings `/settings`                               | Смена ru/en, light/dark/system, long-text previews; pending, быстрое последовательное изменение, ошибка и retry/rollback по контракту; reload; согласованность `/users/me` и локальных preferences; смена системной темы при `system`                                                       | P0/P1     |

Общие состояния применяй к реальным асинхронным компонентам: initial loading, success, empty, no search results, pagination loading/error, mutation pending/success/error. Статусы 403/404/409/422/429/5xx тестируй там, где у endpoint есть соответствующая семантика. Не дублируй каждую ошибку на каждой странице, если она обрабатывается одной общей инфраструктурой.

Особое внимание удели caches: библиотека ↔ каталог ↔ детали ↔ профиль, избранное ↔ home, login/logout, settings и межвкладочные обновления. Сначала проверь поведение без reload, чтобы не скрыть ошибку invalidation; затем reload проверяет сохранение. Не требуй фоновый refetch, если контракт допускает корректное локальное обновление.

### Минимальный набор настоящих integration-цепочек

| ID      | Цепочка                                                                                                                | Что доказывает                                                                  |
| ------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| INT-001 | Login → protected page → reload → logout → прямой protected URL                                                        | Настоящие cookies, proxy, guard и прекращение сессии                            |
| INT-002 | Register в UI → автоматический login → home                                                                            | Реальная регистрация; отдельный лимитированный smoke                            |
| INT-003 | Создать колоду и карточки → связать → изменить → reload → удалить созданное                                            | Write/read контракт и persistence; проверяемые операции через UI                |
| INT-004 | Импорт небольшого JSON → список карточек → reload                                                                      | Реальный импорт и формат результата                                             |
| INT-005 | Подготовленная колода → start → answer/skip → завершение → история                                                     | Реальная проверка ответов, счётчики и история; порядок карточек не предполагать |
| INT-006 | Ответить на часть → reload/уйти → resume → завершить                                                                   | Восстановление серверного прогресса без двойного ответа                         |
| INT-007 | Пользователь B сохраняет публичную колоду A → видит библиотеку; попытка редактировать чужую; private deck недоступен B | Реальные права и viewer state в двух изолированных contexts                     |
| INT-008 | A удаляет/закрывает публичную колоду, сохранённую B → B открывает архив и сохраняет копию                              | Реальный архивный workflow, отношения и данные копии                            |
| INT-009 | Сменить язык/тему/previews → reload и повторный login                                                                  | Persistence настроек и их bootstrap                                             |
| INT-010 | Настоящий login → убрать только access cookie, сохранив refresh → protected request                                    | Настоящий refresh и повтор запроса без ожидания истечения JWT                   |

INT-001/003/005 — первая обязательная тройка. Остальные добавляй после устойчивого seed. При INT-010 cookies можно целенаправленно удалить как предусловие; нельзя подделывать токены или ответы. Для browser-specific smoke повторяй выбранные истории, а не весь объём fixtures.

## 8. Формат отдельного теста

Название: `[ID] условие → наблюдаемый результат`. Русский текст допустим; ID и имена файлов сохраняй стабильными. Один тест проверяет одну историю, может иметь несколько связанных действий и assertions. Независимые истории не связывай порядком запуска или serial describe.

Обязательная карточка сценария перед реализацией:

```text
ID: LIB-DECK-001
Priority / mode / tags: P0 / mocked / @smoke @responsive
Route / actor: /library/decks / авторизованный владелец
Given: пустая библиотека, ru-RU, валидный текущий пользователь
When: открывает создание, вводит название, подтверждает
Then: один POST с ожидаемыми полями; диалог закрыт; новая колода видна;
      после reload колода остаётся
API: POST /decks/create; bootstrap и GET списка по действующему контракту
Projects: основной desktop и выбранные mobile smoke projects
Data / cleanup: новые scenario-local данные; уничтожаются fixture
Evidence: UI assertions, проверка request body, trace при падении
```

В spec используй короткие `test.step`: подготовить → выполнить → проверить. Полную карточку храни в реестре, а не копируй большой комментарий в каждый spec. Метки: `@smoke`, `@responsive`, `@a11y`, `@regression`; mode определяется директорией/project. Конкретную причину regression указывай ссылкой на задачу или описанием бага.

Правила assertions и действий:

- Сначала пользовательский результат, затем важные детали запроса. Assert только HTTP 200 без проверки UI недостаточен.
- Основные locators — `getByRole` с accessible name, `getByLabel`, затем устойчивый `getByTestId` для элемента без естественного имени. Ограничивай поиск конкретным dialog/card/row. Не используй CSS Modules hashes, XPath, цепочки DOM и случайный `nth()`.
- Текст локатора соответствует фиксированной локали; не используй regex, одновременно принимающий русский и английский, чтобы скрыть ошибку языка. Не импортируй весь production словарь как oracle для перевода.
- `await expect(locator).toBeVisible/toHaveText/toHaveURL/...` вместо мгновенных проверок `isVisible()` или `textContent()`. Для измерений используй `expect.poll`.
- Перед кликом регистрируй `waitForResponse`/`waitForRequest`, если проверяется конкретный exchange. Matcher включает method/path и нужные параметры, а не первый любой ответ 200.
- Не используй `waitForTimeout`, `networkidle` как готовность приложения, случайные sleep и глобальное увеличение timeout. Практика отправляет activity-запросы, Vite имеет свою сеть; жди нужный UI или конкретное событие.
- По умолчанию без `force: true`, `dispatchEvent`, JS-click и изменения DOM через evaluate. Они скрывают перекрытие, disabled, focus и другие реальные дефекты. Evaluate допустим для чтения геометрии/состояния браузера и обоснованной подготовки окружения.
- В mobile-сценариях используй touch-действия. Управление клавиатурой проверяй отдельно, не подменяй его вызовом handler. Для файлов используй `setInputFiles`, только если UI действительно имеет file input; текущий JSON-ввод не нужно превращать в upload ради теста.
- Даты, locale, timezone и данные фиксируй. Базовая timezone — `Europe/Moscow`; другую используй явно для проверки границы суток. Управляемые часы применяй к целевым timer-тестам; замороженное browser time не управляет server time.
- Unhandled `pageerror` и неожиданные `console.error` проваливают тест. Ожидаемая browser console ошибка отрицательного HTTP-кейса допускается точечно с причиной; не отключай сбор ошибок целиком.
- Различай ожидаемый HTTP error, отменённый запрос и необработанный request failure. Не объявляй каждый 4xx/5xx падением harness: отрицательные сценарии специально их вызывают.
- Для popup/new page подписывайся до действия. Межвкладочный auth проверяй страницами одного context; разных пользователей — разными contexts.

## 9. Visual regression

Начальный набор: login/register; home filled/empty; library decks full/compact и cards; create/edit/import dialog; catalog preview; deck/editor; archive; profile; practice setup/active/wrong answer/result/history; settings; 404. Для каждого снимка задай точное состояние, theme/locale/project и причину, почему DOM assertions не покрывают риск.

Перед снимком дождись целевых данных, загрузки шрифтов и стабильного UI. Используй `expect(page|locator).toHaveScreenshot` с отключёнными анимациями и скрытой кареткой, если именно анимация не предмет проверки. Отдельно покрывай loading контролируемым response, если его вид важен. Имена описывают состояние: `practice-wrong-answer-dark-ru.png`. Baselines разделяй по project. См. [Playwright: visual comparisons](https://playwright.dev/docs/test-snapshots).

Запускай baseline generation и сравнение в одинаковом Linux-окружении с той же версией браузера, шрифтами и DPR. Начни со строгого сравнения; любые допуски на diff обоснуй конкретным шумом. Не увеличивай их, чтобы спрятать дефект. Mask допустим для неизбежно динамической области, но не для проверяемой формы/результата. В mocked лучше убрать динамичность данными.

Обычно снимай viewport или конкретный компонент. Full-page используй для структуры всей страницы, отдельно проверяя fixed/sticky элементы. Скриншот без утверждённого baseline — артефакт, а не прошедшая regression-проверка.

Нельзя автоматически принимать новые baselines после падения. Сначала изучи actual/expected/diff, установи причину изменения, затем обнови только относящиеся snapshots. Первые baselines нужно визуально проверить: они тоже могут зафиксировать уже существующий дефект. Не включай глобальный `--update-snapshots` в CI.

## 10. Воспроизводимость, CI и диагностика

Каждый тест получает свежий browser context. Mutable mocks и пользовательские данные имеют test scope; общие immutable ресурсы могут иметь worker scope. Test fixture гарантирует teardown при ошибке. См. [Playwright: fixtures](https://playwright.dev/docs/test-fixtures).

- Локально retries = 0. В CI допустим 1 retry для диагностики; прошедший только на повторе тест считается flaky и требует разбирательства. Если закреплённая версия поддерживает `failOnFlakyTests`, включи его в обязательном gate.
- Стартовые пределы: test timeout 30 секунд, assertion timeout 5 секунд. Для обоснованного integration case допустим точечный timeout 60 секунд. Startup timeout задавай отдельно. Не превращай долгий startup в sleep внутри теста.
- В CI включи `forbidOnly`, HTML и машинный отчёт, screenshot on failure, trace `retain-on-failure` (чтобы сохранить первый сбой), video `retain-on-failure` при достаточном бюджете артефактов. Не допускай успешный пустой набор тестов.
- Для integration прикладывай ограниченные backend logs и состояние сервисов при падении. Секреты, credentials, cookie state, персональные данные в публичные artifacts не включай; traces могут содержать request/response тела. Используй только синтетические аккаунты и ограниченное хранение артефактов.
- Тест падает, если стенд недоступен или seed не выполнен; не делай автоматический `skip` при ошибке подключения. Skip для неподдерживаемого API должен иметь конкретную причину и альтернативную проверку.
- До CI воспроизведи целевой тест отдельно и с соседними specs. Для проверки отсутствия flakiness запусти его 3 раза с `--repeat-each=3 --retries=0`; это не замена разбору причин.
- При падении сначала trace/network/console, затем различай product bug, неверный mock/контракт, гонку теста и ошибку окружения. Исправлять ожидание под сломанный продукт нельзя. Если исправление продукта вне scope, зафиксируй воспроизводимый дефект.

Предлагаемые gates после внедрения:

| Запуск                             | Набор                                                                                                                                                                      |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Каждый PR                          | Существующие format/typecheck/lint/Vitest/build; E2E typecheck; весь mocked Chromium; smoke Firefox/WebKit/Android/iOS; visual desktop/mobile; integration INT-001/003/005 |
| Изменение auth/API/мутирующей фичи | Дополнительно все относящиеся integration и browser-sensitive cases                                                                                                        |
| По расписанию / перед релизом      | Весь реализованный integration, полная responsive-матрица, языки/темы, tablet/landscape и targeted regression                                                              |

Измеряй длительность и корректируй распределение, сохраняя критические gates. Не запускай все тесты × браузеры × размеры × темы × языки без анализа риска. В CI устанавливай браузеры и системные зависимости закреплённого Playwright; используй `npm ci`. См. [Playwright: CI](https://playwright.dev/docs/ci).

## 11. Чеклист агента для каждого сценария

Иди по списку; неприменимый пункт отмечай N/A с короткой причиной. Не отмечай выполненным то, что только описал.

### До реализации

- [ ] Прочитал применимые AGENTS и этот файл, проверил `git status` и относящийся diff.
- [ ] Нашёл реальную страницу, UI-действие и backend route/schema; отличил существующее поведение от желаемого.
- [ ] Проверил существующие Vitest/Playwright cases, чтобы не дублировать чистую логику и уже покрытую историю.
- [ ] Добавил ID и карточку в реестр: предусловие, действие, наблюдаемый результат, priority, mode, projects.
- [ ] Выбрал минимальные данные, пользователей и применимые success/error/loading/empty состояния.
- [ ] Для integration подтвердил отдельный стенд, migrations, seed, rate limits, cookies и cleanup.

### Во время реализации

- [ ] Использовал fixture нужного набора; mocks установлены до navigation; неизвестные API-запросы обнаруживаются.
- [ ] Fixtures соответствуют wire-контракту, пагинации, правам, IDs и auth bootstrap.
- [ ] Проверяемое действие выполняется пользователем через UI; предусловия не выполняют за него саму проверку.
- [ ] Locators устойчивы и однозначны; нет произвольных sleep, force clicks, скрытой подмены app state.
- [ ] Есть assertions результата и значимой мутации; ошибка не выдаёт успех; данные формы/прогресс не теряются.
- [ ] Для мутации проверено отражение изменения без reload и, где нужно, persistence после reload/read-back.
- [ ] Применимые viewport/touch/keyboard/long-text случаи выбраны явно; mobile проверяется взаимодействием.
- [ ] Изоляция работает между тестами, retries, проектами и пользователями; teardown обрабатывает падение.
- [ ] Visual baseline просмотрен, окружение зафиксировано, diff не скрыт широким tolerance/mask.

### После реализации

- [ ] Новый/изменённый spec проходит отдельно с retries=0, затем три повтора и затронутый набор в нужных projects.
- [ ] Нет неожиданных page errors, API-запросов, необъяснённых skips и зависимостей от порядка.
- [ ] При добавлении инфраструктуры проверил `playwright test --list`, выбор projects и отсутствие E2E в Vitest discovery.
- [ ] Выполнил применимые format, frontend и E2E typecheck, lint, Vitest, build по `frontend/AGENTS.md`.
- [ ] Обновил реестр, README/команды при изменении harness; не объявил planned cases покрытыми.
- [ ] Просмотрел финальный diff: нет секретов, auth state, actual/diff artifacts и несвязанных изменений.
- [ ] В итоговом отчёте перечислил сценарии/файлы, точные команды и результаты, реально проверенные браузеры/размеры, оставшиеся gaps и найденные дефекты.

## 12. Порядок первого внедрения

1. Создать harness, разделить Vitest и Playwright, добавить TS/lint, строгий mock router, auth fixture, сбор ошибок и артефактов. Проверить один guest и один protected smoke без backend.
2. Реализовать P0 mocked: auth, create/edit/import, start/answer/resume; подключить desktop и два mobile projects, затем smoke остальных движков.
3. Подготовить integration seed/cleanup, cookie/proxy preflight и независимый запуск Compose; провести INT-001/003/005 без моков.
4. Покрыть все остальные зарегистрированные страницы и P1 состояния; добавить race/caches/межвкладочные проверки, keyboard и responsive границы.
5. Создать и просмотреть visual baselines; подключить PR gates, затем расширить integration и scheduled matrix.

Каждый этап заканчивается работающим, проверяемым набором. Если поддержка сценария отсутствует или найден дефект продукта, опиши пробел и способ воспроизведения. Не добавляй фиктивные успешные ответы и ослабленные assertions, чтобы формально закрыть список.
