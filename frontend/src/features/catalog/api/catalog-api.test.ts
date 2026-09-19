import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../../api";
import {
  CATALOG_PAGE_SIZE,
  getCatalogDeckPage,
  getCatalogDeckPreviewInitialData,
  getCatalogPreviewCardPage,
} from "./catalog-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const CATALOG_ITEM = {
  deck: {
    uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
    owner_uuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
    owner_username: "deck-owner",
    title: "Daily Words",
    description: "Core vocabulary",
    words_count: 48,
    saves_count: 12,
    is_public: true,
    updated_at: "2026-07-17T10:30:00Z",
  },
  viewer_state: null,
};

describe("getCatalogDeckPage", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("loads the selected catalog page with 30 decks and a normalized search query", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValue(Array.from({ length: 30 }, () => CATALOG_ITEM));

    await expect(getCatalogDeckPage(4, " travel ", controller.signal)).resolves.toMatchObject({
      page: 4,
      hasMore: true,
    });

    expect(CATALOG_PAGE_SIZE).toBe(30);
    expect(apiFetch).toHaveBeenCalledWith("/bff/catalog", {
      query: { page: 4, limit: 30, q: "travel" },
      signal: controller.signal,
    });
  });
});

describe("catalog deck preview", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("loads card batches with an offset and a limit of 100", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValue([]);

    await expect(
      getCatalogPreviewCardPage(CATALOG_ITEM.deck.uuid, 200, controller.signal),
    ).resolves.toMatchObject({ cards: [], nextOffset: 200, hasMore: false });

    expect(apiFetch).toHaveBeenCalledWith(`/decks/${CATALOG_ITEM.deck.uuid}/cards`, {
      query: { offset: 200, limit: 100 },
      signal: controller.signal,
    });
  });

  it("loads the deck and its first card batch through one facade", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValueOnce(CATALOG_ITEM.deck).mockResolvedValueOnce([]);

    await expect(
      getCatalogDeckPreviewInitialData(CATALOG_ITEM.deck.uuid, controller.signal),
    ).resolves.toMatchObject({
      deck: { uuid: CATALOG_ITEM.deck.uuid, title: CATALOG_ITEM.deck.title },
      cardPage: { cards: [], nextOffset: 0, hasMore: false },
    });

    expect(apiFetch).toHaveBeenNthCalledWith(1, `/decks/${CATALOG_ITEM.deck.uuid}`, {
      signal: controller.signal,
    });
    expect(apiFetch).toHaveBeenNthCalledWith(2, `/decks/${CATALOG_ITEM.deck.uuid}/cards`, {
      query: { offset: 0, limit: 100 },
      signal: controller.signal,
    });
  });
});
