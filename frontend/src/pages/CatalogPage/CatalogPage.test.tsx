import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "../../i18n";

const useAuthMock = vi.hoisted(() => vi.fn());
const useCatalogDecksMock = vi.hoisted(() => vi.fn());

vi.mock("../../auth/hooks/useAuth", () => ({
  useAuth: useAuthMock,
}));

vi.mock("../../features/catalog/model/useCatalogDecks", () => ({
  useCatalogDecks: useCatalogDecksMock,
}));

import { CatalogPage } from "./CatalogPage";

function renderCatalog(pathname = "/catalog"): string {
  return renderToStaticMarkup(
    <LocaleProvider initialLocale="ru-RU">
      <MemoryRouter initialEntries={[pathname]}>
        <CatalogPage />
      </MemoryRouter>
    </LocaleProvider>,
  );
}

describe("CatalogPage", () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    useCatalogDecksMock.mockReset();
    useAuthMock.mockReturnValue({
      user: { uuid: "d2f61c35-11d0-489e-837d-3845418ba39e" },
    });
    useCatalogDecksMock.mockReturnValue({
      status: "success",
      decks: [
        {
          uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
          ownerUuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
          ownerUsername: "deck-owner",
          title: "Daily Words",
          description: "Core vocabulary",
          totalWordsCount: 48,
          savesCount: 12,
          isSaved: false,
          isPublic: true,
          updatedAt: "2026-07-17T10:30:00Z",
        },
      ],
      page: 2,
      hasMore: true,
      error: null,
      savingDeckUuids: [],
      saveErrors: {},
      retry: vi.fn(),
      setSaved: vi.fn(),
    });
  });

  it("renders numbered catalog pagination from the page query", () => {
    const markup = renderCatalog("/catalog?page=2");

    expect(useCatalogDecksMock).toHaveBeenCalledWith("", 2);
    expect(markup).toContain('aria-label="Страницы каталога"');
    expect(markup).toContain('aria-label="Перейти на страницу 1"');
    expect(markup).toContain('aria-label="Страница 2, текущая"');
    expect(markup).toContain('aria-current="page"');
    expect(markup).toContain('aria-label="Перейти на страницу 3"');
    expect(markup).toContain('aria-label="Открыть страницу колоды «Daily Words»"');
    expect(markup).toContain('data-deck-action="open"');
    expect(markup).toContain('href="/decks/714d882d-726e-4dcb-9303-a8bf4638429c"');
    expect(markup).toContain('href="/users/deck-owner"');
    expect(markup).toContain('aria-label="Открыть профиль пользователя @deck-owner"');
    expect(markup).toContain(">@deck-owner</span>");
    expect(markup).not.toContain('<circle cx="12" cy="8.2" r="3.2"');
    expect(markup).not.toContain("Показать ещё");
  });

  it("opens a deck preview from a direct preview query while preserving the catalog page", () => {
    const markup = renderCatalog("/catalog?page=2&preview=714d882d-726e-4dcb-9303-a8bf4638429c");

    expect(useCatalogDecksMock).toHaveBeenCalledWith("", 2);
    expect(markup).toContain("<dialog");
    expect(markup).toContain(">Предпросмотр колоды</span>");
    expect(markup).toContain("Загружаем предпросмотр…");
  });
});
