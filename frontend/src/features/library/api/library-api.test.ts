import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../../api";
import { getLibraryDeckPage } from "./library-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const RESPONSE = { decks: [], next_cursor: null, has_more: false };

describe("getLibraryDeckPage", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(RESPONSE);
  });

  it("loads the exact authenticated BFF route without a first-page cursor", async () => {
    const controller = new AbortController();

    await expect(getLibraryDeckPage(null, controller.signal)).resolves.toEqual({
      decks: [],
      nextCursor: null,
      hasMore: false,
    });

    expect(apiFetch).toHaveBeenCalledWith("/bff/decks", {
      query: { cursor: null },
      signal: controller.signal,
    });
  });

  it("forwards the opaque pagination cursor", async () => {
    await getLibraryDeckPage("opaque-cursor");

    expect(apiFetch).toHaveBeenCalledWith("/bff/decks", {
      query: { cursor: "opaque-cursor" },
      signal: undefined,
    });
  });
});
