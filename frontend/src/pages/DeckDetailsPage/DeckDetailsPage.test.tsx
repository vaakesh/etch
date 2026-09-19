import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api";
import type { UseDeckDetailsResult } from "../../features/decks/model/useDeckDetails";
import { LocaleProvider, type AppLocale } from "../../i18n";

const useDeckDetailsMock = vi.hoisted(() => vi.fn());
const authState = vi.hoisted(() => ({
  userUuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
}));

vi.mock("../../auth/hooks/useAuth", () => ({
  useAuth: () => ({
    status: "authorized",
    user: {
      uuid: authState.userUuid,
      username: "etch-user",
      email: "etch@example.com",
      settings: { locale: "ru-RU", showPreviewsForLong: true, theme: "light" },
    },
  }),
}));

vi.mock("../../features/decks/model/useDeckDetails", () => ({
  useDeckDetails: useDeckDetailsMock,
}));

import { DeckDetailsPage } from "./DeckDetailsPage";

const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const CARD_UUID = "413b1910-5d07-4c67-93a0-6b8946c59b15";

function createDetailsResult(overrides: Partial<UseDeckDetailsResult> = {}): UseDeckDetailsResult {
  return {
    status: "success",
    deck: {
      uuid: DECK_UUID,
      ownerUuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
      ownerUsername: "etch-user",
      title: "Испанский в путешествии",
      description: "Слова для летней поездки",
      totalWordsCount: 700,
      savesCount: 42,
      isPublic: true,
      updatedAt: "2026-09-10T10:00:00Z",
    },
    cards: [
      {
        uuid: CARD_UUID,
        frontText: "путешествие",
        backText: "viaje",
        frontLang: "ru",
        backLang: "es",
        updatedAt: "2026-09-10T10:00:00Z",
      },
    ],
    currentPage: 7,
    pageCount: 14,
    error: null,
    isPageLoading: false,
    pageError: null,
    retry: vi.fn(),
    retryPage: vi.fn(),
    selectPage: vi.fn(),
    updateCard: vi.fn(async () => undefined),
    deleteCard: vi.fn(async () => undefined),
    deleteDeck: vi.fn(async () => undefined),
    ...overrides,
  };
}

function renderPage(locale: AppLocale = "ru-RU", navigationState?: unknown): string {
  return renderToStaticMarkup(
    <LocaleProvider initialLocale={locale}>
      <MemoryRouter initialEntries={[{ pathname: `/decks/${DECK_UUID}`, state: navigationState }]}>
        <Routes>
          <Route element={<DeckDetailsPage />} path="/decks/:deck_uuid" />
        </Routes>
      </MemoryRouter>
    </LocaleProvider>,
  );
}

describe("DeckDetailsPage", () => {
  beforeEach(() => {
    authState.userUuid = "d2f61c35-11d0-489e-837d-3845418ba39e";
    useDeckDetailsMock.mockReset();
    useDeckDetailsMock.mockReturnValue(createDetailsResult());
  });

  it("renders deck metadata, page numbering, and owner management actions", () => {
    const markup = renderPage();

    expect(useDeckDetailsMock).toHaveBeenCalledWith(DECK_UUID);
    expect(markup).toContain("Испанский в путешествии");
    expect(markup).toContain("Слова для летней поездки");
    expect(markup).toContain("700");
    expect(markup).toContain("42");
    expect(markup).toContain("etch-user");
    expect(markup.match(/etch-user/g)).toHaveLength(1);
    expect(markup).toContain(">@etch-user</span>");
    expect(markup).not.toContain("<dt>Владелец</dt>");
    expect(markup).toContain('<time dateTime="2026-09-10T10:00:00Z">');
    expect(markup).toContain(`href="/library/${DECK_UUID}/edit"`);
    expect(markup).toContain("Удалить колоду");
    expect(markup.indexOf("<h1>Испанский в путешествии</h1>")).toBeLessThan(
      markup.indexOf('aria-label="Редактировать колоду"'),
    );
    expect(markup.indexOf("</dl>")).toBeLessThan(markup.indexOf("<time"));
    expect(markup).toContain(`data-card-uuid="${CARD_UUID}"`);
    expect(markup).toContain('aria-label="Карточка 301"');
    expect(markup).toContain('aria-label="Редактировать карточку «путешествие»"');
    expect(markup).toContain('aria-label="Удалить карточку «путешествие»"');
    expect(markup).toContain('aria-label="Страница 7, текущая"');
    expect(markup).toContain('aria-label="Перейти на страницу 8"');
  });

  it("hides all mutation controls when the viewer is not the owner", () => {
    authState.userUuid = "f9b7ced5-fbea-4741-82fd-33ea144dab7c";
    const markup = renderPage();

    expect(markup).toContain("etch-user");
    expect(markup).not.toContain(`href="/library/${DECK_UUID}/edit"`);
    expect(markup).not.toContain("Удалить колоду");
    expect(markup).not.toContain("Редактировать карточку");
    expect(markup).not.toContain("Удалить карточку");
    expect(markup).toContain("Начать тренировку");
  });

  it("renders a private empty deck without pagination", () => {
    useDeckDetailsMock.mockReturnValue(
      createDetailsResult({
        deck: {
          uuid: DECK_UUID,
          ownerUuid: authState.userUuid,
          ownerUsername: "etch-user",
          title: "Пустая колода",
          description: null,
          totalWordsCount: 0,
          savesCount: 0,
          isPublic: false,
          updatedAt: null,
        },
        cards: [],
        currentPage: 1,
        pageCount: 0,
      }),
    );

    const markup = renderPage();

    expect(markup).toContain("Приватная");
    expect(markup).toContain("В этой колоде пока нет карточек");
    expect(markup).not.toContain('aria-label="Страницы карточек"');
  });

  it("keeps inaccessible and missing decks in one safe error state", () => {
    useDeckDetailsMock.mockReturnValue(
      createDetailsResult({
        status: "error",
        deck: null,
        cards: [],
        pageCount: 0,
        error: new ApiError({ status: 403, message: "Internal backend detail" }),
      }),
    );

    const markup = renderPage();

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Колода не найдена или недоступна этой учётной записи.");
    expect(markup).not.toContain("Internal backend detail");
  });

  it("renders the public page labels in English", () => {
    authState.userUuid = "f9b7ced5-fbea-4741-82fd-33ea144dab7c";
    const markup = renderPage("en-US");

    expect(markup).toContain("etch-user");
    expect(markup).toContain("Start practice");
    expect(markup).toContain('aria-label="Card 301"');
  });

  it("returns to the owner profile when opened from a profile deck", () => {
    const markup = renderPage("ru-RU", {
      deckDetailsReturnTarget: "profile",
      profileUsername: "deck-owner",
    });

    expect(markup).toContain('aria-label="Вернуться в профиль"');
    expect(markup).toContain('href="/users/deck-owner"');
  });
});
