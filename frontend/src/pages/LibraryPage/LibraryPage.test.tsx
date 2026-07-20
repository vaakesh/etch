import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../features/library/model/useLibraryDecks", () => ({
  useLibraryDecks: () => ({
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
    retry: vi.fn(),
    loadMore: vi.fn(),
  }),
}));

import { LibraryPage } from "./LibraryPage";

describe("LibraryPage", () => {
  it("renders deck card previews, empty previews, actions, and accessible tabs", () => {
    const markup = renderToStaticMarkup(<LibraryPage />);

    expect(markup).toContain("Библиотека");
    expect(markup).not.toContain('aria-label="Основная навигация"');
    expect(markup).toContain('role="tablist"');
    expect(markup).toContain('id="library-decks-tab"');
    expect(markup).toContain('id="library-cards-tab"');
    expect(markup).toContain('aria-selected="true"');
    expect(markup).toContain("Daily Words");
    expect(markup).toContain("Travel Essentials");
    expect(markup.match(/<article/g)).toHaveLength(2);
    expect(markup.match(/role="meter"/g)).toHaveLength(2);
    expect(markup).toContain('aria-label="В избранном"');
    expect(markup).toContain('aria-label="Не в избранном"');
    expect(markup).toContain("hello");
    expect(markup).toContain("привет");
    expect(markup).toContain("journey");
    expect(markup).toContain("путешествие");
    expect(markup).toContain("Карточек нет");
    expect(markup).toContain("Точность пользователя:");
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
});
