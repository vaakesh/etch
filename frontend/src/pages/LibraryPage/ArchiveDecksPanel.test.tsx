import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "../../i18n";

const useArchiveOffersMock = vi.hoisted(() => vi.fn());
const usePreserveArchivedDeckMock = vi.hoisted(() => vi.fn());
vi.mock("../../features/library/model/useArchivedDecks", () => ({
  useArchiveOffers: useArchiveOffersMock,
  useArchivePreview: vi.fn(),
  usePreserveArchivedDeck: usePreserveArchivedDeckMock,
}));

import { ArchiveDecksPanel } from "./ArchiveDecksPanel";

describe("ArchiveDecksPanel", () => {
  beforeEach(() => {
    useArchiveOffersMock.mockReset();
    usePreserveArchivedDeckMock.mockReturnValue({
      pendingUuid: null,
      failedUuid: null,
      error: null,
      deletedCopyUuid: null,
      preserve: vi.fn(),
    });
  });

  it("shows only returned archive offers and an accessible preview control", () => {
    useArchiveOffersMock.mockReturnValue({
      status: "success",
      offers: [
        {
          uuid: "0199c27d-9a31-7e11-8f08-b193932384e5",
          title: "Старый словарь",
          expiresAt: "2026-10-28T12:00:00Z",
          preservedDeckUuid: null,
        },
      ],
      error: null,
      retry: vi.fn(),
    });

    const markup = renderToStaticMarkup(
      <LocaleProvider initialLocale="ru-RU">
        <MemoryRouter>
          <ArchiveDecksPanel />
        </MemoryRouter>
      </LocaleProvider>,
    );

    expect(markup).toContain("Архивные колоды");
    expect(markup).toContain("Старый словарь");
    expect(markup).toContain("Посмотреть карточки");
    expect(markup).toContain("Восстановить");
    expect(markup).toContain('aria-expanded="false"');
    expect(markup).not.toContain("Daily Words");
  });
});
