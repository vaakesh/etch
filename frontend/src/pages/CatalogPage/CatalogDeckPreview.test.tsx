import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "../../i18n";

const useCatalogDeckPreviewMock = vi.hoisted(() => vi.fn());

vi.mock("../../features/catalog/model/useCatalogDeckPreview", () => ({
  useCatalogDeckPreview: useCatalogDeckPreviewMock,
}));

import { CatalogDeckPreview } from "./CatalogDeckPreview";

const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";

describe("CatalogDeckPreview", () => {
  beforeEach(() => {
    useCatalogDeckPreviewMock.mockReset();
    useCatalogDeckPreviewMock.mockReturnValue({
      status: "success",
      deck: {
        uuid: DECK_UUID,
        ownerUuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
        ownerUsername: "deck-owner",
        title: "Daily Words",
        description: "Core vocabulary",
        totalWordsCount: 2500,
        savesCount: 12,
        isPublic: true,
        updatedAt: "2026-07-17T10:30:00Z",
      },
      cards: [
        {
          uuid: "019c05e5-bc86-70e6-8f5c-d31bfa1aac11",
          frontText: "indelible",
          backText: "неизгладимый",
          frontLang: "en",
          backLang: "ru",
          updatedAt: "2026-07-17T10:30:00Z",
        },
      ],
      currentPage: 56,
      pageCount: 100,
      error: null,
      isPageLoading: false,
      pageError: null,
      retry: vi.fn(),
      retryPage: vi.fn(),
      selectPage: vi.fn(),
    });
  });

  it("renders adaptive numbered pagination with arrows and global card numbering", () => {
    const markup = renderToStaticMarkup(
      <LocaleProvider initialLocale="ru-RU">
        <MemoryRouter>
          <CatalogDeckPreview
            deckUuid={DECK_UUID}
            onClose={vi.fn()}
            onOpenDeck={vi.fn()}
            returnTarget="catalog"
          />
        </MemoryRouter>
      </LocaleProvider>,
    );

    expect(markup).toContain(`href="/decks/${DECK_UUID}"`);
    expect(markup).toContain("deck-owner");
    expect(markup.match(/>@deck-owner<\/span>/g)).toHaveLength(1);
    expect(markup).toContain('aria-label="Автор: @deck-owner"');
    expect(markup).not.toContain("<dt>Владелец</dt>");
    expect(markup).toMatch(/<dt>слов<\/dt><dd>2\u00a0500<\/dd>/);
    expect(markup).toContain("<dt>сохранений</dt><dd>12</dd>");
    expect(markup.indexOf("</dl>")).toBeLessThan(markup.indexOf("<time"));
    expect(markup).toContain('aria-label="Открыть страницу колоды"');
    expect(markup).toContain('aria-label="Страницы карточек"');
    expect(markup).toContain('aria-label="Предыдущая страница"');
    expect(markup).toContain('aria-label="Следующая страница"');
    expect(markup).toContain('aria-label="Страница 56, текущая"');
    expect(markup).toContain('aria-label="Перейти на страницу 54"');
    expect(markup).toContain('aria-label="Перейти на страницу 58"');
    expect(markup).toContain(">1376</span>");
    expect(markup).not.toContain("Показать ещё");
    expect(markup).not.toContain(" из 2500");
  });
});
