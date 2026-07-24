import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { UseDeckEditorResult } from "../../features/library/model/useDeckEditor";

const useDeckEditorMock = vi.hoisted(() => vi.fn());

vi.mock("../../features/library/model/useDeckEditor", () => ({
  useDeckEditor: useDeckEditorMock,
}));

import { LibraryDeckEditPage } from "./LibraryDeckEditPage";

const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const CARD_UUID = "413b1910-5d07-4c67-93a0-6b8946c59b15";

function createEditorResult(overrides: Partial<UseDeckEditorResult> = {}): UseDeckEditorResult {
  return {
    status: "success",
    deck: {
      uuid: DECK_UUID,
      title: "Испанский в путешествии",
      description: "Слова для летней поездки",
      totalWordsCount: 51,
      isPublic: false,
      updatedAt: "2026-07-24T18:30:00Z",
    },
    cards: [
      {
        uuid: CARD_UUID,
        frontText: "путешествие",
        backText: "viaje",
        sourceLang: "ru",
        targetLang: "es",
        updatedAt: "2026-07-24T18:30:00Z",
      },
    ],
    nextOffset: 50,
    hasMore: true,
    error: null,
    isLoadingMore: false,
    loadMoreError: null,
    retry: vi.fn(),
    loadMore: vi.fn(),
    saveDeck: vi.fn(async () => undefined),
    updateCard: vi.fn(async () => undefined),
    removeCard: vi.fn(async () => undefined),
    ...overrides,
  };
}

function renderEditor(path = `/library/${DECK_UUID}/edit`): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<LibraryDeckEditPage />} path="/library/:deck_uuid/edit" />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LibraryDeckEditPage", () => {
  beforeEach(() => {
    useDeckEditorMock.mockReset();
    useDeckEditorMock.mockReturnValue(createEditorResult());
  });

  it("renders the loading state and passes the route UUID to the editor hook", () => {
    useDeckEditorMock.mockReturnValue(
      createEditorResult({
        status: "loading",
        deck: null,
        cards: [],
        nextOffset: 0,
        hasMore: false,
      }),
    );

    const markup = renderEditor();

    expect(useDeckEditorMock).toHaveBeenCalledWith(DECK_UUID);
    expect(markup).toContain('aria-label="Загрузка редактора колоды"');
    expect(markup).toContain('role="status"');
    expect(markup).not.toContain("О колоде");
  });

  it("renders the error state with retry and an exact library href", () => {
    useDeckEditorMock.mockReturnValue(
      createEditorResult({
        status: "error",
        deck: null,
        cards: [],
        nextOffset: 0,
        hasMore: false,
        error: new Error("failed"),
      }),
    );

    const markup = renderEditor();

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Колода не загрузилась");
    expect(markup).toContain("Не удалось загрузить колоду. Попробуйте ещё раз.");
    expect(markup).toMatch(/<a[^>]*href="\/library"[^>]*>Вернуться в библиотеку<\/a>/);
    expect(markup).toContain("Попробовать снова");
  });

  it("renders editable deck fields, a compact card row, scoped actions, and load more", () => {
    const markup = renderEditor();
    const backLink = markup.match(/<a[^>]*aria-label="Вернуться в библиотеку"[^>]*>/)?.[0];
    const cardRow = markup.match(
      new RegExp(`<li[^>]*data-card-uuid="${CARD_UUID}"[^>]*>[\\s\\S]*?</li>`),
    )?.[0];

    expect(markup).toContain("Редактор колоды");
    expect(markup).toContain("<h1");
    expect(markup).toContain("Испанский в путешествии");
    expect(markup).toContain(`data-deck-details-form="${DECK_UUID}"`);
    expect(markup).toMatch(
      /<input[^>]*maxLength="150"[^>]*name="title"[^>]*value="Испанский в путешествии"/,
    );
    expect(markup).toMatch(
      /<textarea[^>]*name="description"[^>]*>Слова для летней поездки<\/textarea>/,
    );
    expect(markup).toContain("Приватная");
    expect(markup).toContain("Сохранить изменения");

    expect(backLink).toBeDefined();
    expect(backLink).toContain('href="/library"');

    expect(cardRow).toBeDefined();
    expect(cardRow).toContain("viaje");
    expect(cardRow).toContain("путешествие");
    expect(cardRow).toContain('data-card-action="edit"');
    expect(cardRow).toContain('data-card-action="remove-from-deck"');
    expect(cardRow).toContain("Удалить из колоды");
    expect(cardRow).toContain('title="Удалить карточку только из этой колоды"');
    expect(cardRow).not.toContain('data-card-action="add-to-deck"');
    expect(cardRow).not.toContain('data-card-action="delete"');
    expect(cardRow).not.toContain('title="Удалить карточку"');
    expect(cardRow?.match(/data-card-action=/g)).toHaveLength(2);

    expect(markup).toContain("Загрузить больше");
    expect(markup).not.toContain("Добавить в колоду");
  });

  it("renders the empty deck state without card actions or load more", () => {
    useDeckEditorMock.mockReturnValue(
      createEditorResult({
        deck: {
          uuid: DECK_UUID,
          title: "Пустая колода",
          description: null,
          totalWordsCount: 0,
          isPublic: true,
          updatedAt: null,
        },
        cards: [],
        nextOffset: 0,
        hasMore: false,
      }),
    );

    const markup = renderEditor();

    expect(markup).toContain("В этой колоде пока нет карточек");
    expect(markup).toContain("Добавить карточки можно из вкладки «Карточки» в библиотеке.");
    expect(markup).toMatch(/<a[^>]*href="\/library"[^>]*>Открыть библиотеку<\/a>/);
    expect(markup).not.toContain("data-card-uuid");
    expect(markup).not.toContain("data-card-action");
    expect(markup).not.toContain("Загрузить больше");
  });
});
