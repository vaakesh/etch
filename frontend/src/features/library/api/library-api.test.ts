import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../../api";
import {
  getFavouriteLibraryDeckPage,
  getLibraryDeckPage,
  setLibraryDeckFavourite,
} from "./library-api";

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

  it.each([true, false])("sets favourite=%s through the deck PATCH route query", async (value) => {
    vi.mocked(apiFetch).mockResolvedValue({ is_favourite: value });
    const controller = new AbortController();

    await expect(
      setLibraryDeckFavourite("714d882d-726e-4dcb-9303-a8bf4638429c", value, controller.signal),
    ).resolves.toEqual({ isFavourite: value });

    expect(apiFetch).toHaveBeenCalledWith(
      "/decks/714d882d-726e-4dcb-9303-a8bf4638429c/set-favourite",
      {
        method: "PATCH",
        query: { value },
        signal: controller.signal,
      },
    );
  });

  it("rejects a favourite response without the boolean state", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ is_favourite: "yes" });

    await expect(
      setLibraryDeckFavourite("714d882d-726e-4dcb-9303-a8bf4638429c", true),
    ).rejects.toMatchObject({
      status: 0,
      code: "INVALID_FAVOURITE_RESPONSE",
    });
  });
});

describe("getFavouriteLibraryDeckPage", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(RESPONSE);
  });

  it("loads the exact favourite BFF route without a trailing slash", async () => {
    const controller = new AbortController();

    await expect(getFavouriteLibraryDeckPage(null, controller.signal)).resolves.toEqual({
      decks: [],
      nextCursor: null,
      hasMore: false,
    });

    expect(apiFetch).toHaveBeenCalledWith("/bff/decks/favourite", {
      query: { cursor: null },
      signal: controller.signal,
    });
  });

  it("forwards the opaque favourite-page cursor", async () => {
    await getFavouriteLibraryDeckPage("opaque-favourite-cursor");

    expect(apiFetch).toHaveBeenCalledWith("/bff/decks/favourite", {
      query: { cursor: "opaque-favourite-cursor" },
      signal: undefined,
    });
  });
});
