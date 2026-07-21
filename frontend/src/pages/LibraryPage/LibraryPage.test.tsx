import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const useLibraryDecksMock = vi.hoisted(() => vi.fn());

vi.mock("../../features/library/model/useLibraryDecks", () => ({
  useLibraryDecks: useLibraryDecksMock,
}));

function createLibraryResult(overrides: Record<string, unknown> = {}) {
  return {
    status: "success",
    decks: [
      {
        uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
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
          },
          {
            uuid: "28dd615b-a6cb-4471-8238-b41c25556bb0",
            frontText: "journey",
            backText: "путешествие",
          },
        ],
      },
      {
        uuid: "f9b7ced5-fbea-4741-82fd-33ea144dab7c",
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
    onlyFavourites: false,
    retry: vi.fn(),
    loadMore: vi.fn(),
    setOnlyFavourites: vi.fn(),
    setFavourite: vi.fn(),
    ...overrides,
  };
}

import { LibraryPage } from "./LibraryPage";

describe("LibraryPage", () => {
  beforeEach(() => {
    useLibraryDecksMock.mockReturnValue(createLibraryResult());
  });

  it("renders deck card previews, empty previews, actions, and accessible tabs", () => {
    const markup = renderToStaticMarkup(<LibraryPage />);
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
    expect(markup).toMatch(
      /<button[^>]*aria-controls="library-decks-panel"[^>]*aria-pressed="false"/,
    );
    expect(markup).toContain("Daily Words");
    expect(markup).toContain("Travel Essentials");
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
    expect(markup).toContain("Начать");
    expect(markup).toContain("Всего слов: 48");
    expect(markup).toContain("Последнее обновление:");
    expect(markup).not.toContain("Открыть");
    expect(markup).not.toContain('viewBox="0 0 160 140"');
    expect(markup).toContain("2</strong> колод загружено");
    expect(markup).toMatch(/<section[^>]*hidden=""[^>]*id="library-cards-panel"[^>]*><\/section>/);
    expect(markup).toContain("Новая колода");
    expect(markup.match(/ disabled=""/g)?.length).toBeGreaterThanOrEqual(5);
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
            isFollowing: false,
            cards: [
              {
                uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
                frontText: "etch",
                backText: "гравировать",
              },
            ],
          },
        ],
      }),
    );

    const markup = renderToStaticMarkup(<LibraryPage />);

    expect(markup).toMatch(
      /<button[^>]*aria-controls="library-decks-panel"[^>]*aria-pressed="true"/,
    );
    expect(markup).toContain('data-deck-uuid="714d882d-726e-4dcb-9303-a8bf4638429c"');
    expect(markup).toContain("Backend favourites");
    expect(markup).toContain('aria-valuetext="91%"');
    expect(markup).toMatch(/<span[^>]*role="meter"[^>]*tabindex="0">91<\/span>/);
    expect(markup).toContain('aria-label="Удалить из избранного: «Backend favourites»"');
    expect(markup).toContain('aria-pressed="true"');
    expect(markup).toContain("1</strong> любимых колод загружено");
  });

  it("shows a dedicated empty state for the favourite filter", () => {
    useLibraryDecksMock.mockReturnValue(
      createLibraryResult({
        decks: [],
        onlyFavourites: true,
      }),
    );

    const markup = renderToStaticMarkup(<LibraryPage />);

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

    const markup = renderToStaticMarkup(<LibraryPage />);

    expect(markup).not.toContain("Любимых колод пока нет");
    expect(markup).toContain("Показать ещё");
  });
});
