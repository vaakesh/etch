import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../../api";
import { CATALOG_PAGE_SIZE, getCatalogDeckPage } from "./catalog-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const CATALOG_ITEM = {
  deck: {
    uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
    owner_uuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
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
