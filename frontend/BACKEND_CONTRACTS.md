# Карта контрактов Frontend ↔ Backend

> [!NOTE]
> Снимок актуален для рабочего backend на **2026-08-01**. Здесь перечислены только те backend-endpoint-ы, которые frontend действительно вызывает. Источник истины при расхождении — route, schema и runtime handler в <code>/backend</code>.

## Быстрая карта

| Frontend / consumer                                   | Backend-вызовы                                                                                                                                                                                                                                             |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Запуск приложения                                     | <code>GET /users/me</code>; при <code>401</code> — <code>POST /auth/refresh</code> и один повтор                                                                                                                                                           |
| <code>/login</code>                                   | <code>POST /auth/login</code> → <code>GET /users/me</code>                                                                                                                                                                                                 |
| <code>/</code>                                        | <code>GET /bff/home</code>                                                                                                                                                                                                                                 |
| <code>/library</code>, колоды                         | <code>GET /bff/library/decks</code>, <code>POST /decks/create</code>, <code>PATCH /decks/{deck_uuid}/set-favourite</code>                                                                                                                                  |
| <code>/library</code>, карточки                       | <code>GET /bff/library/cards</code>, <code>POST /cards/</code>, <code>PATCH/DELETE /cards/{card_uuid}</code>                                                                                                                                               |
| Добавление карточки в колоды                          | <code>GET /users/me/decks</code>, <code>POST /decks/{deck_uuid}/cards/{card_uuid}</code>                                                                                                                                                                   |
| <code>/library/:deck_uuid/edit</code>                 | <code>GET/PATCH /decks/{deck_uuid}</code>, <code>GET /decks/{deck_uuid}/cards</code>, <code>PATCH /cards/{card_uuid}</code>, <code>POST /decks/{deck_uuid}/cards/remove/{card_uuid}</code>                                                                 |
| <code>/practice</code>                                | <code>GET /users/me/training-sessions</code>, <code>POST /bff/practice/{deck_uuid}/start</code>, <code>GET /bff/practice/{training_session_uuid}/resume</code>, <code>PUT /training-sessions/{training_session_uuid}/items/{sequence_number}/submit</code> |
| <code>/practice/sessions/:session_uuid/history</code> | <code>GET /training-sessions/{session_uuid}/history</code>                                                                                                                                                                                                 |
| Logout / очистка сессии                               | <code>POST /auth/logout</code>                                                                                                                                                                                                                             |
| <code>*</code> (404)                                  | Backend-вызовов нет                                                                                                                                                                                                                                        |

Всего: **26 frontend-вызовов / 24 уникальные пары method + path**. Два варианта списка колод используют один endpoint с разным <code>is_favourite</code>, а проверка колоды перед практикой повторно использует <code>GET /decks/{deck_uuid}</code>.

## Общие правила транспорта

- В коде указывается backend-path без префикса <code>/api</code>. Browser URL собирается из <code>VITE_API_URL</code> (по умолчанию <code>/api</code>) и path.
- Все запросы приложения отправляют cookies через <code>credentials: "include"</code>.
- Объект в <code>body</code> сериализуется как JSON с <code>Content-Type: application/json</code>.
- <code>null</code> и <code>undefined</code> в query не попадают в URL.
- Обычный защищённый запрос после <code>401</code> вызывает один <code>POST /auth/refresh</code>, затем исходный запрос повторяется не более одного раза.
- Login, refresh и logout выполняются с <code>auth: false</code> и без автоматического retry, но cookies всё равно отправляются.
- <code>Cursor</code> непрозрачен для frontend: его можно только сохранить и вернуть backend без декодирования.

## Общие wire-типы

```ts
type UUID = string; // UUID в строковом wire-формате
type DateTime = string; // ISO 8601 date-time
type DateOnly = string; // YYYY-MM-DD
type Cursor = string; // opaque

type CursorPage<T> = {
  items: T[];
  next_cursor: Cursor | null;
  has_more: boolean;
};

type PrivateUserOut = {
  uuid: UUID;
  username: string;
  email: string;
  created_at: DateTime;
  updated_at: DateTime;
};

type HomeDashboard = {
  decks: DeckDashboard[];
  progress: UserProgress;
  user_weekly_activity: WeeklyActivityDay[];
};

type DeckDashboard = {
  deck_uuid: UUID;
  owner_uuid: UUID;
  title: string;
  description: string | null;
  deck_words_count: number; // int
  user_accuracy: number; // int
  updated_at: DateTime | null;
};

type UserProgress = {
  user_words_explored: number; // int
  user_weekly_accuracy: number; // float допустим
  user_current_streak: number; // int, дни
  user_total_study_time: number; // int, секунды
};

type WeeklyActivityDay = {
  date: DateOnly;
  percent: number; // int, 0..100
};

type CardLibraryPage = {
  card_uuid: UUID;
  front_text: CardText;
  back_text: CardText;
  source_lang: CardLang;
  target_lang: CardLang;
  updated_at: DateTime;
};

type DeckLibraryPage = {
  deck_uuid: UUID;
  owner_uuid: UUID;
  title: string;
  description: string | null;
  deck_words_count: number; // int
  user_accuracy: number; // int
  is_favourite: boolean;
  updated_at: DateTime | null;
  cards: CardLibraryPage[];
};

type DeckDetail = {
  uuid: UUID;
  title: string;
  description: string | null;
  words_count: number; // int
  is_public: boolean;
  updated_at: DateTime | null;
};

type CardDetail = {
  uuid: UUID;
  front_text: CardText;
  back_text: CardText;
  source_lang: CardLang;
  target_lang: CardLang;
}; // updated_at здесь нет

type DeckCardDetail = {
  deck_uuid: UUID;
  card_uuid: UUID;
  position: number; // int
};

type CardSide = "front" | "back";

type PracticeCard = {
  sequence_number: number; // int, >= 1; позиция в колоде, может быть разреженной и больше total_count
  prompt_text: string;
  prompt_language: string;
  answer_language: string;
};

type PracticeSessionResponse = {
  training_session_uuid: UUID;
  deck_uuid: UUID;
  prompt_side: CardSide;
  answer_side: CardSide;
  total_count: number; // int
  answered_count: number; // int
  correct_count: number; // int
  wrong_count: number; // int
  started_at: DateTime;
  cards: PracticeCard[];
};

type UserAnswer = { action: "answer"; answer: string } | { action: "skip"; answer?: null };

type SubmitAnswerResponse = {
  is_correct: boolean;
  answer_text: string;
  answered_count: number; // int
  correct_count: number; // int
  total_count: number; // int
  is_finished: boolean;
  time_to_complete: number | null; // int, секунды
};

type TrainingSessionItemOut = {
  item_uuid: UUID;
  sequence_number: number; // int, >= 1
  prompt_text: CardText;
  answer_text: CardText;
  prompt_lang: CardLang;
  answer_lang: CardLang;
  user_typed_text: CardText | null;
  is_answered: boolean;
  is_correct: boolean | null;
};
```

### Ограничения и нормализация

| Тип                          | Backend-правило                                     |
| ---------------------------- | --------------------------------------------------- |
| <code>Username</code>        | trim + lowercase, 3–18 символов, без whitespace     |
| <code>Password</code>        | 8–128 символов, без whitespace; регистр сохраняется |
| <code>CardText</code>        | trim + lowercase, 1–255 символов                    |
| <code>CardLang</code>        | trim + lowercase, 2–3 символа                       |
| <code>DeckTitle</code>       | trim, 3–50 символов                                 |
| <code>DeckDescription</code> | trim, до 3000 символов, nullable                    |

## Auth и сессия

### <code>POST /auth/login</code>

- **Consumer:** <code>/login</code>.
- **Auth:** не требуется; auto-refresh выключен.
- **Body, JSON:** <code>{ username: Username; password: Password }</code>, оба поля обязательны.
- **Success:** <code>204</code>, body отсутствует. Backend устанавливает <code>access_token</code> и <code>refresh_token</code> как <code>HttpOnly; Secure; SameSite=Lax; Path=/</code>. Токены в JSON не возвращаются.
- **Default cookie lifetime:** access — 50 минут, refresh — 7 дней (может изменяться конфигурацией).
- **Ошибки:** <code>404</code> неверные credentials; <code>422</code> validation; <code>500</code>.

### <code>GET /users/me</code>

- **Consumer:** bootstrap, post-login identity, явная синхронизация auth.
- **Auth:** access cookie.
- **Request:** без query/body.
- **Success:** <code>200 PrivateUserOut</code>.
- **Frontend использует:** <code>uuid</code>, <code>username</code>, <code>email</code>. Поля <code>created_at</code> и <code>updated_at</code> намеренно не сохраняются в auth state.
- **Ошибки:** <code>401</code> отсутствующий/невалидный access token; <code>404</code> пользователь исчез; <code>500</code>.

### <code>POST /auth/refresh</code>

- **Consumer:** автоматический или явный refresh.
- **Auth:** refresh cookie; access cookie не обязателен; auto-refresh для самого запроса выключен.
- **Request:** без body.
- **Success:** <code>204</code>, ротация обеих cookies.
- **Ошибки:** <code>401</code> refresh cookie отсутствует, истёк, невалиден или уже использован; возможны <code>404</code> и <code>500</code>.

### <code>POST /auth/logout</code>

- **Consumer:** logout и безопасная очистка неудавшегося login.
- **Auth:** refresh cookie опционален.
- **Request:** без body.
- **Success:** <code>200</code>; body frontend не использует. Активная refresh-сессия отзывается, обе cookies очищаются. Отсутствующая cookie — успешный idempotent logout.

## Главная

### <code>GET /bff/home</code>

- **Frontend:** <code>/</code>.
- **Auth:** обязателен.
- **Request:** без query/body.
- **Success:** <code>200 HomeDashboard</code>.
- **Mapping:** <code>deck_uuid → uuid</code>, <code>owner_uuid → ownerUuid</code>, <code>deck_words_count → totalWordsCount</code>, <code>user_accuracy → accuracy</code>, progress/activity переводятся из snake_case в camelCase.
- **Ошибки:** <code>401</code>, возможные <code>404</code> и <code>500</code>.

## Библиотека: списки

### <code>GET /bff/library/decks</code>

- **Frontend:** <code>/library</code>, список колод и фильтр «Только любимые».
- **Auth:** обязателен.
- **Query:**
  - <code>q: string | null</code> (trim + lowercase, 1–150), поиск по словам в названии;
  - <code>cursor: Cursor | null = null</code>;
  - <code>is_favourite: boolean | null = false</code>;
  - <code>limit: int = 50</code>, диапазон 1–100.
- **Фактические вызовы:** frontend отправляет <code>limit=50</code> и явный <code>is_favourite=false/true</code>. Непустой поиск передаётся как trimmed <code>q</code> после debounce; при смене поиска или фильтра cursor сбрасывается.
- **Success:** <code>200 CursorPage&lt;DeckLibraryPage&gt;</code>.
- **Mapping:** <code>items → decks</code>, <code>deck_uuid → uuid</code>, <code>owner_uuid → ownerUuid</code>, <code>deck_words_count → totalWordsCount</code>, <code>next_cursor → nextCursor</code>. Preview-карточки используют <code>card_uuid</code>, <code>front_text</code>, <code>back_text</code>, <code>source_lang</code>, <code>target_lang</code> и <code>updated_at</code>.
- **Ошибки:** <code>401</code>, <code>422</code> query/cursor, возможные <code>404</code> и <code>500</code>.

Кнопки редактирования и удаления показываются только при совпадении <code>owner_uuid</code> с UUID текущего пользователя.

### <code>GET /bff/library/cards</code>

- **Frontend:** вкладка карточек в <code>/library</code>.
- **Auth:** обязателен.
- **Query:** <code>cursor: Cursor | null = null</code>, <code>limit: int = 50</code>. Сейчас backend не задаёт <code>ge/le</code> для limit.
- **Фактический вызов:** frontend отправляет <code>limit=50</code>.
- **Success:** <code>200 CursorPage&lt;CardLibraryPage&gt;</code>.
- **Mapping:** <code>items → cards</code>, <code>next_cursor → nextCursor</code>; у карточки только <code>card_uuid</code> имеет префикс, остальные поля — обычные <code>front_text</code>, <code>updated_at</code> и т. д. <code>owner_uuid</code> отсутствует.
- **Ошибки:** <code>401</code>, <code>422</code>, <code>500</code>.

## Библиотека: создание и изменение

### <code>POST /decks/create</code>

- **Frontend:** dialog создания колоды.
- **Auth:** обязателен.
- **Body, JSON:** <code>{ title: DeckTitle; description?: DeckDescription = null; is_public?: boolean = false }</code>. Frontend отправляет все три поля.
- **Success:** <code>200 DeckDetail</code>.
- **Ошибки:** <code>401</code>, <code>409</code> duplicate, <code>422</code>, <code>500</code>.
- **Важно:** canonical path без trailing slash; старый <code>POST /decks/</code> больше не используется.

### <code>POST /cards/</code>

- **Frontend:** dialog создания карточки.
- **Auth:** обязателен.
- **Body, JSON:** <code>{ front_text: CardText; back_text: CardText; source_lang?: CardLang = "ru"; target_lang?: CardLang = "en" }</code>. Frontend отправляет все четыре поля.
- **Success:** <code>200 CardDetail</code>.
- **Ошибки:** <code>401</code>, <code>409</code> duplicate, <code>422</code>, <code>500</code>.
- **Важно:** trailing slash является частью canonical path.

### <code>PATCH /cards/{card_uuid}</code>

- **Frontend:** редактирование карточки в библиотеке и editor колоды.
- **Auth:** обязателен.
- **Path:** <code>card_uuid: UUID</code>.
- **Body, JSON:** backend принимает optional/nullable <code>front_text</code>, <code>back_text</code>, <code>source_lang</code>, <code>target_lang</code> и игнорирует <code>null</code>. Frontend всегда отправляет четыре non-null поля.
- **Success:** <code>200 CardDetail</code>. В ответе **нет <code>updated_at</code>**.
- **Ошибки:** <code>401</code>, <code>403</code> не владелец, <code>404</code>, <code>409</code> duplicate, <code>422</code>, <code>500</code>.

### <code>DELETE /cards/{card_uuid}</code>

- **Frontend:** удаление из вкладки карточек.
- **Auth:** обязателен.
- **Path:** <code>card_uuid: UUID</code>; body отсутствует.
- **Success:** <code>204</code>, body отсутствует. После успеха frontend обновляет список колод, потому что меняются counts.
- **Ошибки:** <code>401</code>, <code>404</code> карточка отсутствует или скрывается non-owner, <code>422</code>, <code>500</code>.

### <code>PATCH /decks/{deck_uuid}/set-favourite</code>

- **Frontend:** heart-action на колоде.
- **Auth:** обязателен.
- **Path/query:** <code>deck_uuid: UUID</code>, <code>value: boolean = true</code>. Frontend всегда отправляет value явно; body отсутствует.
- **Success:** <code>200</code> с **raw JSON boolean**: <code>true</code> или <code>false</code>, не объект.
- **Ошибки:** <code>401</code>, <code>404</code> колода отсутствует или приватна, <code>409</code> снятие favourite без user-deck state, <code>422</code>, <code>500</code>.

> [!WARNING]
> Обычный library-response может содержать приватные колоды, но <code>set-favourite</code> разрешает только публичные; <code>DeckLibraryPage</code> не содержит <code>is_public</code>. Frontend не может заранее корректно отключить heart-action для приватной колоды.

## Добавление карточки в колоды

### <code>GET /users/me/decks</code>

- **Frontend:** список вариантов в dialog «Добавить в колоду».
- **Auth:** обязателен.
- **Query:** <code>limit: int = 30</code> (1–100), <code>q: string | null</code> (trim + lowercase, 1–150), <code>cursor: Cursor | null</code> (до 512 символов).
- **Фактический вызов:** frontend запрашивает <code>limit=100</code> и последовательно проходит все cursor-страницы; <code>q</code> не отправляет.
- **Success:** <code>200 CursorPage&lt;DeckDetail&gt;</code>, не bare array.
- **Frontend использует:** <code>uuid</code>, <code>title</code>, <code>words_count</code>.
- **Ошибки:** <code>401</code>, <code>404</code>, <code>422</code>, <code>500</code>.

### <code>POST /decks/{deck_uuid}/cards/{card_uuid}</code>

- **Frontend:** добавление выбранной карточки в одну колоду.
- **Auth:** обязателен.
- **Path:** два UUID; query/body отсутствуют.
- **Success:** <code>200 DeckCardDetail</code>; frontend body не использует.
- **Особое поведение:** <code>409</code> преобразуется frontend в статус <code>already-present</code>, остальные ошибки остаются ошибками конкретной колоды.
- **Ошибки:** <code>401</code>, <code>403</code> deck/card не принадлежат пользователю, <code>404</code>, <code>409</code>, <code>422</code>, <code>500</code>.

## Редактор колоды

### <code>GET /decks/{deck_uuid}</code>

- **Frontend:** metadata для <code>/library/:deck_uuid/edit</code>.
- **Backend auth:** опционален; frontend route защищён.
- **Success:** <code>200 DeckDetail</code>. Публичная колода доступна без auth, приватная — только владельцу.
- **Ошибки:** <code>404</code> отсутствующая или недоступная приватная колода; <code>401</code> при невалидной переданной cookie; <code>422</code>; <code>500</code>.

### <code>PATCH /decks/{deck_uuid}</code>

- **Frontend:** сохранение metadata editor-а.
- **Auth:** обязателен.
- **Body, JSON:** <code>{ title?: DeckTitle; description?: DeckDescription; is_public?: boolean }</code>. Явный <code>null</code> запрещён для title/is_public; <code>description: null</code> очищает описание. Frontend отправляет только title + description.
- **Success:** <code>200 DeckDetail</code>.
- **Ошибки:** <code>401</code>, <code>403</code> не владелец, <code>404</code>, <code>409</code> duplicate, <code>422</code>, <code>500</code>.

### <code>GET /decks/{deck_uuid}/cards</code>

- **Frontend:** карточки editor-а; первый запрос выполняется параллельно с metadata.
- **Backend auth:** опционален; frontend route защищён.
- **Query:** <code>offset: int = 0</code>, минимум 0; <code>limit: int = 50</code>, диапазон 1–50.
- **Success:** <code>200 CardDetail[]</code>, без page-envelope и без <code>updated_at</code>.
- **Frontend pagination:** <code>nextOffset = offset + items.length</code>, <code>hasMore = items.length === limit</code>. Для точного кратного 50 возможен один безопасный дополнительный пустой запрос.
- **Ошибки:** <code>404</code> отсутствующая/недоступная колода, <code>401</code> при невалидной cookie, <code>422</code>, <code>500</code>.

### <code>POST /decks/{deck_uuid}/cards/remove/{card_uuid}</code>

- **Frontend:** удалить связь card ↔ deck, не саму карточку.
- **Auth:** обязателен.
- **Request:** два UUID в path, без body.
- **Success:** <code>204</code>, body отсутствует.
- **Ошибки:** <code>401</code>, <code>403</code> deck/card не принадлежат пользователю, <code>404</code> deck/card/link отсутствует, <code>422</code>, <code>500</code>.

## Практика

Маршрут frontend — <code>/practice</code>. Query <code>deck={deck_uuid}</code> открывает настройку и запуск новой сессии, а <code>session={training_session_uuid}</code> — продолжение уже созданной сессии. Одновременно используется только один из этих вариантов. Детали отдельной сессии открываются на <code>/practice/sessions/:session_uuid/history</code>.

### <code>POST /bff/practice/{deck_uuid}/start</code>

- **Frontend:** <code>/practice?deck={deck_uuid}</code>, запуск после выбора стороны вопроса.
- **Auth:** обязателен.
- **Path:** <code>deck_uuid: UUID</code>; query отсутствует.
- **Body, JSON:** <code>{ prompt_side: CardSide }</code>, поле обязательно. <code>answer_side</code> backend выбирает как противоположную сторону.
- **Количество карточек:** параметра количества в текущем контракте нет. Backend создаёт snapshot всех карточек колоды в порядке их позиций; frontend предлагает только вариант «Все карточки».
- **Success:** <code>200 PracticeSessionResponse</code>. При <code>prompt_side="front"</code> вопрос и его язык берутся из <code>front_text/source_lang</code>, ответ — из <code>back_text/target_lang</code>; при <code>"back"</code> стороны меняются местами.
- **Важно:** <code>cards</code> содержит текст вопроса и языки, но не содержит правильный ответ. <code>sequence_number</code> является устойчивой исходной позицией карточки в колоде: после удалений номера могут иметь пропуски и быть больше <code>total_count</code>.
- **Ошибки:** <code>401</code>; <code>403</code> чужая приватная колода; <code>404</code> колода не найдена; <code>409</code> пустая колода; <code>422</code> UUID/body; <code>500</code>.

### <code>GET /bff/practice/{training_session_uuid}/resume</code>

- **Frontend:** <code>/practice?session={training_session_uuid}</code>.
- **Auth:** обязателен.
- **Path:** <code>training_session_uuid: UUID</code>; query/body отсутствуют.
- **Success:** <code>200 PracticeSessionResponse</code>. В <code>cards</code> возвращаются только ещё не отвеченные элементы, отсортированные по исходному <code>sequence_number</code>; counters и <code>total_count</code> относятся ко всей сессии.
- **Frontend navigation:** нельзя вычислять wire-номер как индекс массива + 1. Для отображения номера и отправки ответа frontend использует <code>PracticeCard.sequence_number</code>, потому что после resume первый оставшийся элемент может иметь любой номер.
- **Ошибки:** <code>401</code>; <code>404</code> сессия отсутствует, принадлежит другому пользователю или связанная колода исчезла; <code>409</code> сессия уже завершена; <code>422</code> UUID; <code>500</code>.

### <code>GET /training-sessions/{session_uuid}/history</code>

- **Frontend:** <code>/practice/sessions/:session_uuid/history</code>, переход по компактной кнопке в карточке сессии.
- **Auth:** обязателен; backend выбирает только элементы сессии текущего пользователя.
- **Query:** <code>ps: int = 30</code>, диапазон 1–100; <code>pn: int = 1</code>, минимум 1; <code>only_answered_items: boolean = false</code>. Frontend запрашивает страницы по 100 элементов до первой неполной страницы.
- **Success:** <code>200 TrainingSessionItemOut[]</code>, без page-envelope. Frontend сортирует итог по <code>sequence_number</code>, проверяет уникальность item UUID и номеров.
- **Отображение:** <code>is_answered=false</code> означает неотвеченную карточку — она показывается нейтрально, без раскрытия правильного ответа. Для отвеченной карточки <code>user_typed_text=null</code> означает пропуск. Непустой <code>user_typed_text</code> — введённый ответ: правильный подсвечивается зелёным, неправильный — красным рядом с правильным зелёным ответом.
- **Ошибки:** <code>401</code>; <code>422</code> UUID/query; возможные <code>500</code>.

### <code>PUT /training-sessions/{training_session_uuid}/items/{sequence_number}/submit</code>

- **Frontend:** форма ответа в активной сессии <code>/practice?session={training_session_uuid}</code>.
- **Auth:** обязателен.
- **Path:** <code>training_session_uuid: UUID</code>, <code>sequence_number: int</code>, минимум 1. Frontend передаёт номер непосредственно из соответствующего <code>PracticeCard</code>.
- **Body, JSON:** обычный ответ — <code>{ action: "answer"; answer: string }</code>. Backend делает trim, запрещает пустую строку и сравнивает её с правильным ответом без учёта регистра, но в остальном точным совпадением. Wire-контракт также принимает пропуск <code>{ action: "skip" }</code> или <code>{ action: "skip"; answer: null }</code>; пропуск считается неправильным ответом.
- **Success:** <code>200 SubmitAnswerResponse</code>. <code>is_correct</code> управляет feedback-состоянием, а <code>answer_text</code> содержит правильный ответ для показа пользователю. <code>wrong_count</code> в этом ответе отсутствует и при необходимости вычисляется как <code>answered_count - correct_count</code>.
- **Завершение:** <code>time_to_complete</code> равно <code>null</code> до последнего ответа и содержит целое число секунд после завершения; <code>is_finished</code> явно сообщает о завершении.
- **Повтор:** повторная отправка уже отвеченного элемента идемпотентна — backend возвращает <code>200</code> с сохранёнными <code>is_correct</code> и <code>answer_text</code>, не увеличивая counters.
- **Ошибки:** <code>401</code>; <code>404</code> сессия отсутствует/чужая или элемента с таким <code>sequence_number</code> нет; <code>409</code> сессия уже завершена, но целевой элемент не был отвечен; <code>422</code> UUID, номер или body, включая пустой ответ; <code>500</code>.

## Runtime-ошибки

OpenAPI сейчас не описывает большинство auth/domain errors и показывает стандартную FastAPI-схему для <code>422</code>. Фактические custom handlers возвращают:

```ts
type DomainError = {
  message: string;
}; // обычно 401 / 403 / 404 / 409 / 500

type ValidationError = {
  message: "Validation error";
  details: Array<{
    type: string;
    loc: Array<string | number>;
    msg: string;
    input?: unknown;
    ctx?: Record<string, unknown>;
  }>;
}; // 422
```

- Для необработанного <code>500</code>: <code>{ "message": "Internal server error" }</code>.
- Backend сейчас не возвращает поле <code>code</code>. Значения вроде <code>NETWORK_ERROR</code>, <code>REQUEST_ABORTED</code>, <code>INVALID_HOME_RESPONSE</code>, <code>INVALID_LIBRARY_RESPONSE</code> и <code>INVALID_PRACTICE_RESPONSE</code> создаёт frontend API/contract layer.
- <code>status: 0</code> существует только на frontend и означает transport/client/contract error, а не HTTP status.

## Известные backend-ограничения

Эти пункты нельзя исправить только изменением wire-format frontend:

1. <code>GET /bff/home</code> и обычный <code>GET /bff/library/decks</code> ожидают <code>UserDeck</code> для каждой колоды, но создание колоды его не создаёт. Новая/ещё не изучавшаяся колода может привести к <code>500</code>.
2. При первом добавлении колоды в favourite backend создаёт объект <code>UserDeck</code>, но сейчас не добавляет его в repository. Ответ <code>true</code> может не сохраниться.
3. Favourite deck contract не отдаёт владельца, а обычный deck contract — публичность. Из-за этого frontend не может точно вывести права editor/favourite только по BFF-ответу.

## Что проверять при следующем изменении backend

1. Найти endpoint в быстрой карте.
2. Сравнить method, exact path/trailing slash, auth, query/body и success status.
3. Сравнить envelope (<code>items/next_cursor/has_more</code>) и раскрытые wire-типы.
4. Проверить nullable vs optional и ограничения строк/чисел.
5. Если изменилось только поле, которое frontend явно не использует, менять UI обычно не нужно; обновить эту карту всё равно полезно.
6. Обновить API/contract tests соответствующей feature, затем запустить <code>npm run typecheck</code>, <code>npm run lint</code> и <code>npm run test</code>.
