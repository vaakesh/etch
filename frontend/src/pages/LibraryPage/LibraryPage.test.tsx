import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LIBRARY_CREATE_DECK_NAVIGATION_STATE } from "../../features/library/model/library-navigation";
import type { UseCardDeckAssignmentResult } from "../../features/library/model/useCardDeckAssignment";
import type { UseLibraryCardsResult } from "../../features/library/model/useLibraryCards";
import { LocaleProvider, type AppLocale } from "../../i18n";

const useLibraryDecksMock = vi.hoisted(() => vi.fn());
const useLibraryCardsMock = vi.hoisted(() => vi.fn());
const useCardDeckAssignmentMock = vi.hoisted(() => vi.fn());
const useAuthMock = vi.hoisted(() => vi.fn());

vi.mock("../../auth/hooks/useAuth", () => ({
  useAuth: useAuthMock,
}));
vi.mock("../../features/library/model/useLibraryDecks", () => ({
  useLibraryDecks: useLibraryDecksMock,
}));
vi.mock("../../features/library/model/useLibraryCards", () => ({
  useLibraryCards: useLibraryCardsMock,
}));
vi.mock("../../features/library/model/useCardDeckAssignment", () => ({
  useCardDeckAssignment: useCardDeckAssignmentMock,
}));

function createLibraryResult(overrides: Record<string, unknown> = {}) {
  return {
    status: "success",
    decks: [
      {
        uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
        ownerUuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
        title: "Daily Words",
        description: "Core vocabulary",
        totalWordsCount: 48,
        accuracy: 88,
        isFavourite: true,
        updatedAt: "2026-07-17T10:30:00Z",
        cards: [
          {
            uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
            frontText: "hello",
            backText: "привет",
            frontLang: "en",
            backLang: "ru",
            updatedAt: "2026-07-20T09:15:00Z",
          },
          {
            uuid: "28dd615b-a6cb-4471-8238-b41c25556bb0",
            frontText: "journey",
            backText: "путешествие",
            frontLang: "en",
            backLang: "ru",
            updatedAt: "2026-07-20T09:15:00Z",
          },
        ],
      },
      {
        uuid: "f9b7ced5-fbea-4741-82fd-33ea144dab7c",
        ownerUuid: "aaa61c35-11d0-489e-837d-3845418ba39e",
        title: "Travel Essentials",
        description: null,
        totalWordsCount: 36,
        accuracy: 64,
        isFavourite: false,
        updatedAt: null,
        cards: [],
      },
    ],
    nextCursor: null,
    hasMore: false,
    error: null,
    isLoadingMore: false,
    loadMoreError: null,
    favouriteUpdatingDeckUuids: [],
    favouriteErrors: {},
    deletingDeckUuids: [],
    deleteErrors: {},
    onlyFavourites: false,
    retry: vi.fn(),
    loadMore: vi.fn(),
    createDeck: vi.fn(async () => undefined),
    importCards: vi.fn(async () => ({ importedCount: 1, cards: [] })),
    deleteDeck: vi.fn(),
    setOnlyFavourites: vi.fn(),
    setFavourite: vi.fn(),
    ...overrides,
  };
}

function createCardLibraryResult(
  overrides: Partial<UseLibraryCardsResult> = {},
): UseLibraryCardsResult {
  return {
    status: "success",
    cards: [
      {
        uuid: "8f449a33-87ff-4cf8-a371-43c681623f61",
        frontText: "indelible",
        backText: "неизгладимый",
        frontLang: "en",
        backLang: "ru",
        updatedAt: "2026-07-20T09:15:00Z",
      },
    ],
    nextCursor: null,
    hasMore: false,
    error: null,
    isLoadingMore: false,
    loadMoreError: null,
    retry: vi.fn(),
    loadMore: vi.fn(),
    createCard: vi.fn(async () => undefined),
    updateCard: vi.fn(async () => undefined),
    deleteCard: vi.fn(async () => undefined),
    ...overrides,
  };
}

function createCardDeckAssignmentResult(
  overrides: Partial<UseCardDeckAssignmentResult> = {},
): UseCardDeckAssignmentResult {
  return {
    status: "success",
    decks: [
      {
        uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
        title: "Daily Words",
        totalWordsCount: 48,
      },
      {
        uuid: "f9b7ced5-fbea-4741-82fd-33ea144dab7c",
        title: "Первая поездка",
        totalWordsCount: 1,
      },
    ],
    error: null,
    retry: vi.fn(),
    assignToDecks: vi.fn(async () => []),
    ...overrides,
  };
}

import { AddCardToDeckDialog } from "./AddCardToDeckDialog";
import { CardImportDialog } from "./CardImportDialog";
import { CardEditorDialog } from "./CardEditorDialog";
import { DeckCreatorDialog } from "./DeckCreatorDialog";
import {
  LibraryCardsPanel,
  LibraryCreateButton,
  LibraryImportButton,
  LibraryPage,
} from "./LibraryPage";

function renderLibraryPage(state?: unknown, locale: AppLocale = "ru-RU"): string {
  return renderToStaticMarkup(
    <LocaleProvider initialLocale={locale}>
      <MemoryRouter initialEntries={[{ pathname: "/library", state }]}>
        <LibraryPage />
      </MemoryRouter>
    </LocaleProvider>,
  );
}

describe("LibraryPage", () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    useLibraryDecksMock.mockReset();
    useLibraryCardsMock.mockReset();
    useCardDeckAssignmentMock.mockReset();
    useLibraryDecksMock.mockReturnValue(createLibraryResult());
    useLibraryCardsMock.mockReturnValue(createCardLibraryResult());
    useCardDeckAssignmentMock.mockReturnValue(createCardDeckAssignmentResult());
    useAuthMock.mockReturnValue({
      status: "authorized",
      user: {
        uuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
        username: "etch-user",
        email: "etch@example.com",
        settings: { locale: "ru-RU", showPreviewsForLong: true, theme: "light" },
      },
      error: null,
      isAuthenticated: true,
      initialize: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
      applyUserSettings: vi.fn(),
    });
  });

  it("renders deck card previews, empty previews, actions, and accessible tabs", () => {
    const markup = renderLibraryPage();
    const accuracyTooltipIds = [...markup.matchAll(/aria-describedby="([^"]+)"/g)].map(
      ([, id]) => id,
    );

    expect(markup).toContain("Библиотека");
    expect(markup).not.toContain('aria-label="Основная навигация"');
    expect(markup).toContain('role="tablist"');
    expect(markup).toContain('id="library-decks-tab"');
    expect(markup).toContain('id="library-cards-tab"');
    expect(markup).toContain('aria-selected="true"');
    expect(markup).toContain("Только любимые");
    expect(markup).toContain('name="deck_search"');
    expect(markup).toContain('type="search"');
    expect(markup).toContain('placeholder="Поиск по колодам"');
    expect(markup).toContain('maxLength="150"');
    expect(markup).toContain("Поиск по названию колоды");
    expect(markup).toMatch(
      /<button[^>]*aria-controls="library-decks-panel"[^>]*aria-pressed="false"/,
    );
    expect(markup).toContain("Daily Words");
    expect(markup).toContain("Travel Essentials");
    expect(markup.match(/Описание колоды:/g)).toHaveLength(2);
    expect(markup.match(/<article/g)).toHaveLength(2);
    expect(markup.match(/role="meter"/g)).toHaveLength(2);
    expect(markup).toContain('aria-label="Удалить из избранного: «Daily Words»"');
    expect(markup).toContain('aria-label="Добавить в избранное: «Travel Essentials»"');
    expect(markup).toContain('aria-pressed="true"');
    expect(markup).toContain('aria-pressed="false"');
    expect(markup).toContain("hello");
    expect(markup).toContain("привет");
    expect(markup).toContain("journey");
    expect(markup).toContain("путешествие");
    expect(markup).toContain("Карточек нет");
    expect(markup).not.toContain("Точность пользователя:");
    expect(markup.match(/aria-label="Точность колоды"/g)).toHaveLength(2);
    expect(markup).toContain('aria-valuetext="88%"');
    expect(markup).toContain('aria-valuetext="64%"');
    expect(markup).toMatch(/<span[^>]*role="meter"[^>]*tabindex="0">88<\/span>/);
    expect(markup).toMatch(/<span[^>]*role="meter"[^>]*tabindex="0">64<\/span>/);
    expect(new Set(accuracyTooltipIds).size).toBe(2);
    accuracyTooltipIds.forEach((id) => expect(markup).toContain(`id="${id}"`));
    expect(markup.match(/role="tooltip"/g)).toHaveLength(2);
    expect(markup).toContain("Правильных ответов — 88%");
    expect(markup).toContain("Редактировать");
    expect(markup).toContain('href="/library/714d882d-726e-4dcb-9303-a8bf4638429c/edit"');
    expect(markup).toContain("Начать");
    expect(markup).toContain('href="/practice?deck=714d882d-726e-4dcb-9303-a8bf4638429c"');
    expect(markup).toContain('href="/practice?deck=f9b7ced5-fbea-4741-82fd-33ea144dab7c"');
    expect(markup).toContain("48 слов");
    expect(markup).toContain("Обновлено");
    expect(markup).not.toContain("Открыть");
    expect(markup).not.toContain('viewBox="0 0 160 140"');
    expect(markup).toContain("2</strong> колоды загружены");
    expect(markup).toMatch(/<section[^>]*hidden=""[^>]*id="library-cards-panel"[^>]*><\/section>/);
    expect(markup).not.toContain('data-card-uuid="8f449a33-87ff-4cf8-a371-43c681623f61"');
    expect(useLibraryCardsMock).toHaveBeenCalledWith({
      enabled: false,
      onDeleteSuccess: expect.any(Function),
    });
    expect(markup).toContain("Новая колода");
    expect(markup).toContain("Импорт");
    expect(markup).toContain('title="Импортировать карточки из JSON"');
    expect(markup).not.toContain('data-deck-creator="new"');
    expect(markup).not.toContain('data-card-import="true"');
  });

  it("opens the existing deck creator after navigation from the home action", () => {
    const markup = renderLibraryPage(LIBRARY_CREATE_DECK_NAVIGATION_STATE);

    expect(markup).toContain('data-deck-creator="new"');
    expect(markup).toContain('aria-modal="true"');
    expect(markup).toContain("Новая колода");
  });

  it("removes long-text title previews when they are disabled in user settings", () => {
    useAuthMock.mockReturnValue({
      status: "authorized",
      user: {
        uuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
        username: "etch-user",
        email: "etch@example.com",
        settings: { locale: "ru-RU", showPreviewsForLong: false, theme: "light" },
      },
      error: null,
      isAuthenticated: true,
      initialize: vi.fn(),
      login: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
      applyUserSettings: vi.fn(),
    });

    const markup = renderLibraryPage();

    expect(markup).not.toContain('<h2 title="Daily Words">');
    expect(markup).toContain("Daily Words");
  });

  it("refreshes deck counts after a card is deleted successfully", () => {
    const retryDecks = vi.fn();
    useLibraryDecksMock.mockReturnValue(createLibraryResult({ retry: retryDecks }));

    renderLibraryPage();

    expect(useLibraryCardsMock).toHaveBeenCalledWith({
      enabled: false,
      onDeleteSuccess: retryDecks,
    });
  });

  it("changes the create button label with the active library view", () => {
    const onCreateCard = vi.fn();
    const onCreateDeck = vi.fn();
    const decksMarkup = renderToStaticMarkup(
      <LibraryCreateButton
        activeView="decks"
        onCreateCard={onCreateCard}
        onCreateDeck={onCreateDeck}
      />,
    );
    const cardsMarkup = renderToStaticMarkup(
      <LibraryCreateButton
        activeView="cards"
        onCreateCard={onCreateCard}
        onCreateDeck={onCreateDeck}
      />,
    );

    expect(decksMarkup).toContain("Новая колода");
    expect(decksMarkup).not.toContain("Новая карточка");
    expect(decksMarkup).not.toContain("disabled");
    expect(decksMarkup).toContain('title="Создать новую колоду"');
    expect(cardsMarkup).toContain("Новая карточка");
    expect(cardsMarkup).not.toContain("Новая колода");
    expect(cardsMarkup).not.toContain("disabled");
    expect(cardsMarkup).toContain('title="Создать новую карточку"');
  });

  it("renders the compact JSON import action", () => {
    const markup = renderToStaticMarkup(<LibraryImportButton onImport={vi.fn()} />);

    expect(markup).toContain("Импорт");
    expect(markup).toContain('title="Импортировать карточки из JSON"');
    expect(markup).toContain('type="button"');
  });

  it("starts the import dialog with help and the already loaded deck options", () => {
    const markup = renderToStaticMarkup(
      <LocaleProvider initialLocale="ru-RU">
        <CardImportDialog
          decks={createLibraryResult().decks.slice(0, 1)}
          onClose={vi.fn()}
          onImport={vi.fn(async () => ({ importedCount: 1, cards: [] }))}
        />
      </LocaleProvider>,
    );

    expect(markup).toContain('data-card-import="true"');
    expect(markup).toContain('aria-modal="true"');
    expect(markup).toContain("Как это работает");
    expect(markup).toContain("Формат JSON");
    expect(markup).toContain("Daily Words");
    expect(markup).toContain("48 слов");
    expect(markup).toContain('name="deck_uuid"');
    expect(markup).not.toContain("Travel Essentials");
  });

  it("renders accessible compact cards and active actions after the panel is opened", () => {
    const cardLibrary = createCardLibraryResult({
      hasMore: true,
      nextCursor: "next-card-page",
    });

    const markup = renderToStaticMarkup(
      <LibraryCardsPanel cardLibrary={cardLibrary} isHidden={false} />,
    );
    const actionsTrigger = markup.match(
      /<button[^>]*aria-label="Действия с карточкой «неизгладимый»"[^>]*id="([^"]+)"[^>]*popoverTarget="([^"]+)"/,
    );

    expect(markup).toContain('id="library-cards-panel"');
    expect(markup).not.toContain(" hidden=");
    expect(markup).toContain('tabindex="0"');
    expect(markup).toContain('data-card-uuid="8f449a33-87ff-4cf8-a371-43c681623f61"');
    expect(markup).toContain('lang="en"');
    expect(markup).toContain('lang="ru"');
    expect(markup).toContain("indelible");
    expect(markup).toContain("неизгладимый");
    expect(markup).toContain("EN");
    expect(markup).toContain("RU");
    expect(markup).not.toContain("<span>Слово</span>");
    expect(markup).not.toContain("<span>Перевод</span>");
    expect(markup.indexOf("неизгладимый")).toBeLessThan(markup.indexOf("indelible"));
    expect(markup).not.toContain("Поменять слово и перевод местами");
    expect(markup).not.toContain('dateTime="2026-07-20T09:15:00Z"');
    expect(markup).not.toContain("Обновлено");
    expect(markup).not.toContain("карточка загружена");
    expect(markup).toContain("Показать ещё");
    expect(actionsTrigger).not.toBeNull();
    expect(markup).toContain(`aria-labelledby="${actionsTrigger?.[1]}"`);
    expect(markup).toContain(`id="${actionsTrigger?.[2]}" popover="auto" role="group"`);
    expect(markup).toContain('data-card-action="edit"');
    expect(markup).toContain('data-card-action="add-to-deck"');
    expect(markup).toContain('data-card-action="delete"');
    expect(markup).toContain("Редактировать");
    expect(markup).toContain("Добавить в колоду");
    expect(markup).toContain("Удалить");
    expect(markup).not.toContain("скоро");
    expect(markup).toContain('aria-haspopup="dialog"');
    expect(markup).toContain('title="Добавить карточку в одну или несколько колод"');
    expect(markup).not.toMatch(/data-card-action="[^"]+" disabled=""/);
    expect(markup).not.toMatch(/data-card-action="edit" disabled=""/);
    expect(markup).not.toMatch(/data-card-action="delete" disabled=""/);
    expect(markup).not.toContain("<header");
    expect(markup).not.toContain("<footer");
  });

  it("renders the card editor with all PATCH contract fields", () => {
    const markup = renderToStaticMarkup(
      <CardEditorDialog
        card={createCardLibraryResult().cards[0]}
        onClose={vi.fn()}
        onSave={vi.fn(async () => undefined)}
      />,
    );

    expect(markup).toContain('aria-modal="true"');
    expect(markup).toContain("Редактировать карточку");
    expect(markup).toContain('name="front_text"');
    expect(markup).toContain('name="back_text"');
    expect(markup).toContain('name="front_lang"');
    expect(markup).toContain('name="back_lang"');
    expect(markup.match(/maxLength="255"/g)).toHaveLength(2);
    expect(markup.match(/maxLength="3"/g)).toHaveLength(2);
    expect(markup.match(/minLength="2"/g)).toHaveLength(2);
    expect(markup).toContain("indelible");
    expect(markup).toContain("неизгладимый");
    expect(markup).toContain("Сохранить");
    expect(markup).toContain("Отмена");
  });

  it("renders the deck picker with compact multi-select rows and save action", () => {
    const card = createCardLibraryResult().cards[0];
    if (card === undefined) {
      throw new Error("Expected a card fixture.");
    }

    const markup = renderToStaticMarkup(<AddCardToDeckDialog card={card} onClose={vi.fn()} />);

    expect(useCardDeckAssignmentMock).toHaveBeenCalledWith(card.uuid);
    expect(markup).toContain('aria-modal="true"');
    expect(markup).toContain(`data-card-deck-picker="${card.uuid}"`);
    expect(markup).toContain("Быстрое добавление");
    expect(markup).toContain("Добавить в колоду");
    expect(markup).toContain("Daily Words");
    expect(markup).toContain("Первая поездка");
    expect(markup).toContain("48 слов");
    expect(markup).toContain("1 слово");
    expect(markup.match(/name="deck_uuid"/g)).toHaveLength(2);
    expect(markup.match(/type="checkbox"/g)).toHaveLength(2);
    expect(markup).toContain("0 колод выбрано");
    expect(markup).toMatch(/<button[^>]*disabled=""[^>]*type="submit"[^>]*>/);
    expect(markup).toContain("Сохранить");
    expect(markup).toContain("Отмена");
  });

  it("renders loading, empty, and error states for the deck picker", () => {
    const card = createCardLibraryResult().cards[0];
    if (card === undefined) {
      throw new Error("Expected a card fixture.");
    }

    useCardDeckAssignmentMock.mockReturnValue(
      createCardDeckAssignmentResult({ status: "loading", decks: [] }),
    );
    expect(renderToStaticMarkup(<AddCardToDeckDialog card={card} onClose={vi.fn()} />)).toContain(
      'aria-label="Загрузка ваших колод"',
    );

    useCardDeckAssignmentMock.mockReturnValue(
      createCardDeckAssignmentResult({ status: "success", decks: [] }),
    );
    expect(renderToStaticMarkup(<AddCardToDeckDialog card={card} onClose={vi.fn()} />)).toContain(
      "У вас пока нет колод",
    );

    useCardDeckAssignmentMock.mockReturnValue(
      createCardDeckAssignmentResult({
        status: "error",
        decks: [],
        error: new Error("failed"),
      }),
    );
    const errorMarkup = renderToStaticMarkup(<AddCardToDeckDialog card={card} onClose={vi.fn()} />);
    expect(errorMarkup).toContain("Колоды не загрузились");
    expect(errorMarkup).toContain("Попробовать снова");
  });

  it("renders the new-card editor with empty required fields", () => {
    const markup = renderToStaticMarkup(
      <CardEditorDialog card={null} onClose={vi.fn()} onSave={vi.fn(async () => undefined)} />,
    );

    expect(markup).toContain('data-card-editor="new"');
    expect(markup).toContain("Новая карточка");
    expect(markup).toContain("Заполните тексты и языки обеих сторон.");
    expect(markup.match(/required=""/g)).toHaveLength(4);
    expect(markup.match(/aria-hidden="true">\*<\/span>/g)).toHaveLength(4);
    expect(markup.match(/<textarea[^>]*><\/textarea>/g)).toHaveLength(2);
    expect(markup.match(/value=""/g)).toHaveLength(2);
    expect(markup).toContain("Создать");
    expect(markup).toContain("Карточка появится в библиотеке после создания.");
  });

  it("renders the deck creator with optional description and private default", () => {
    const markup = renderToStaticMarkup(
      <DeckCreatorDialog onClose={vi.fn()} onSave={vi.fn(async () => undefined)} />,
    );

    expect(markup).toContain('data-deck-creator="new"');
    expect(markup).toContain("Новая колода");
    expect(markup).toContain('name="title"');
    expect(markup).toContain('maxLength="50"');
    expect(markup).toContain('minLength="3"');
    expect(markup).toContain('aria-hidden="true">*</span>');
    expect(markup).toContain('name="description"');
    expect(markup).toContain("необязательно");
    expect(markup.match(/name="is_public"/g)).toHaveLength(2);
    expect(markup).toMatch(
      /<input[^>]*type="radio"[^>]*name="is_public"[^>]*checked=""[^>]*value="false"/,
    );
    expect(markup).toContain("Приватная");
    expect(markup).toContain("Публичная");
    expect(markup).toContain("Новая колода появится первой в вашей библиотеке.");
  });

  it("renders loading, empty, and error states for the cards panel", () => {
    const loadingLibrary = createCardLibraryResult({ status: "loading", cards: [] });
    expect(
      renderToStaticMarkup(<LibraryCardsPanel cardLibrary={loadingLibrary} isHidden={false} />),
    ).toContain('aria-label="Загрузка карточек"');

    const emptyLibrary = createCardLibraryResult({ cards: [] });
    expect(
      renderToStaticMarkup(<LibraryCardsPanel cardLibrary={emptyLibrary} isHidden={false} />),
    ).toContain("Карточек пока нет");

    const errorLibrary = createCardLibraryResult({
      status: "error",
      cards: [],
      error: new Error("failed"),
    });
    const errorMarkup = renderToStaticMarkup(
      <LibraryCardsPanel cardLibrary={errorLibrary} isHidden={false} />,
    );
    expect(errorMarkup).toContain("Карточки не загрузились");
    expect(errorMarkup).toContain("Попробовать снова");
  });

  it("renders the favourite endpoint UUID and accuracy fields", () => {
    useLibraryDecksMock.mockReturnValue(
      createLibraryResult({
        onlyFavourites: true,
        decks: [
          {
            uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
            ownerUuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
            title: "Backend favourites",
            description: null,
            totalWordsCount: 12,
            accuracy: 91,
            updatedAt: "2026-07-20T09:15:00Z",
            isFavourite: true,
            cards: [
              {
                uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
                frontText: "etch",
                backText: "гравировать",
                frontLang: "en",
                backLang: "ru",
                updatedAt: "2026-07-20T09:15:00Z",
              },
            ],
          },
        ],
      }),
    );

    const markup = renderLibraryPage();

    expect(markup).toMatch(
      /<button[^>]*aria-controls="library-decks-panel"[^>]*aria-pressed="true"/,
    );
    expect(markup).toContain('data-deck-uuid="714d882d-726e-4dcb-9303-a8bf4638429c"');
    expect(markup).toContain("Backend favourites");
    expect(markup).toContain('aria-valuetext="91%"');
    expect(markup).toMatch(/<span[^>]*role="meter"[^>]*tabindex="0">91<\/span>/);
    expect(markup).toContain('aria-label="Удалить из избранного: «Backend favourites»"');
    expect(markup).toContain('aria-pressed="true"');
    expect(markup).toContain("1</strong> любимая колода загружена");
  });

  it("does not expose deck management for another user's favourite deck", () => {
    useLibraryDecksMock.mockReturnValue(
      createLibraryResult({
        onlyFavourites: true,
        decks: [
          {
            uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
            ownerUuid: "aaa61c35-11d0-489e-837d-3845418ba39e",
            title: "Чужая публичная колода",
            description: null,
            totalWordsCount: 12,
            accuracy: 91,
            updatedAt: "2026-07-20T09:15:00Z",
            isFavourite: true,
            cards: [],
          },
        ],
      }),
    );

    const markup = renderLibraryPage();

    expect(markup).not.toContain('href="/library/714d882d-726e-4dcb-9303-a8bf4638429c/edit"');
    expect(markup).not.toContain('aria-label="Удалить колоду «Чужая публичная колода»"');
  });

  it("shows a dedicated empty state for the favourite filter", () => {
    useLibraryDecksMock.mockReturnValue(
      createLibraryResult({
        decks: [],
        onlyFavourites: true,
      }),
    );

    const markup = renderLibraryPage();

    expect(markup).toContain("Любимых колод пока нет");
    expect(markup).toContain("Добавьте колоды в любимые, и они появятся здесь.");
  });

  it("keeps favourite pagination available after the loaded cards are removed", () => {
    useLibraryDecksMock.mockReturnValue(
      createLibraryResult({
        decks: [],
        hasMore: true,
        nextCursor: "next-favourite-page",
        onlyFavourites: true,
      }),
    );

    const markup = renderLibraryPage();

    expect(markup).not.toContain("Любимых колод пока нет");
    expect(markup).toContain("Показать ещё");
  });

  it("renders the library page controls in English", () => {
    const markup = renderLibraryPage(undefined, "en-US");

    expect(markup).toContain("Library");
    expect(markup).toContain("Decks");
    expect(markup).toContain("Cards");
    expect(markup).toContain("Favorites only");
    expect(markup).toContain('placeholder="Search decks"');
    expect(markup).toContain("Deck accuracy");
  });
});
