import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../../api";
import {
  createLibraryCard,
  createLibraryDeck,
  deleteLibraryCard,
  getFavouriteLibraryDeckPage,
  getLibraryCardPage,
  getLibraryDeckPage,
  setLibraryDeckFavourite,
  updateLibraryCard,
} from "./library-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const RESPONSE = { decks: [], next_cursor: null, has_more: false };

describe("createLibraryDeck", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue({
      uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
      title: "Испанский в путешествии",
      description: null,
      words_count: 0,
      is_public: false,
      version: 1,
      created_at: "2026-07-21T18:30:00Z",
      updated_at: "2026-07-21T18:30:00Z",
    });
  });

  it("posts the exact deck creation contract and maps DeckOut", async () => {
    const controller = new AbortController();

    await expect(
      createLibraryDeck(
        {
          title: "Испанский в путешествии",
          description: null,
          isPublic: false,
        },
        controller.signal,
      ),
    ).resolves.toEqual({
      uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
      title: "Испанский в путешествии",
      description: null,
      totalWordsCount: 0,
      isPublic: false,
      updatedAt: "2026-07-21T18:30:00Z",
    });

    expect(apiFetch).toHaveBeenCalledWith("/decks/", {
      method: "POST",
      body: {
        title: "Испанский в путешествии",
        description: null,
        is_public: false,
      },
      signal: controller.signal,
    });
  });

  it("rejects a created deck without a usable UUID", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      uuid: null,
      title: "Без UUID",
      description: null,
      words_count: 0,
      is_public: false,
      updated_at: null,
    });

    await expect(
      createLibraryDeck({ title: "Без UUID", description: null, isPublic: false }),
    ).rejects.toMatchObject({
      status: 0,
      code: "INVALID_LIBRARY_RESPONSE",
    });
  });
});

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

describe("getLibraryCardPage", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue({ cards: [], cursor: null, has_more: false });
  });

  it("loads the exact card library route without a trailing slash or first-page cursor", async () => {
    const controller = new AbortController();

    await expect(getLibraryCardPage(null, controller.signal)).resolves.toEqual({
      cards: [],
      nextCursor: null,
      hasMore: false,
    });

    expect(apiFetch).toHaveBeenCalledWith("/bff/library/cards", {
      query: { cursor: null },
      signal: controller.signal,
    });
  });

  it("forwards the opaque card cursor", async () => {
    await getLibraryCardPage("opaque-card-cursor");

    expect(apiFetch).toHaveBeenCalledWith("/bff/library/cards", {
      query: { cursor: "opaque-card-cursor" },
      signal: undefined,
    });
  });
});

describe("createLibraryCard", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue({
      uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
      front_text: "привет",
      back_text: "hello",
      source_lang: "ru",
      target_lang: "en",
    });
  });

  it("posts all fields to the exact card creation route and maps CardOut", async () => {
    const controller = new AbortController();

    await expect(
      createLibraryCard(
        {
          frontText: "привет",
          backText: "hello",
          sourceLang: "ru",
          targetLang: "en",
        },
        controller.signal,
      ),
    ).resolves.toEqual({
      uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
      frontText: "привет",
      backText: "hello",
      sourceLang: "ru",
      targetLang: "en",
    });

    expect(apiFetch).toHaveBeenCalledWith("/cards/", {
      method: "POST",
      body: {
        front_text: "привет",
        back_text: "hello",
        source_lang: "ru",
        target_lang: "en",
      },
      signal: controller.signal,
    });
  });

  it("rejects an invalid created-card response", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
      front_text: "привет",
    });

    await expect(
      createLibraryCard({
        frontText: "привет",
        backText: "hello",
        sourceLang: "ru",
        targetLang: "en",
      }),
    ).rejects.toMatchObject({
      status: 0,
      code: "INVALID_LIBRARY_RESPONSE",
    });
  });
});

describe("updateLibraryCard", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue({
      id: 17,
      uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
      user_id: 4,
      front_text: "неизгладимый",
      back_text: "indelible",
      source_lang: "ru",
      target_lang: "en",
      created_at: "2026-07-19T09:15:00Z",
      updated_at: "2026-07-21T18:30:00Z",
    });
  });

  it("patches the exact card route and maps the updated card response", async () => {
    const controller = new AbortController();

    await expect(
      updateLibraryCard(
        "413b1910-5d07-4c67-93a0-6b8946c59b15",
        {
          frontText: "неизгладимый",
          backText: "indelible",
          sourceLang: "ru",
          targetLang: "en",
        },
        controller.signal,
      ),
    ).resolves.toEqual({
      uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
      frontText: "неизгладимый",
      backText: "indelible",
      sourceLang: "ru",
      targetLang: "en",
      updatedAt: "2026-07-21T18:30:00Z",
    });

    expect(apiFetch).toHaveBeenCalledWith("/cards/413b1910-5d07-4c67-93a0-6b8946c59b15", {
      method: "PATCH",
      body: {
        front_text: "неизгладимый",
        back_text: "indelible",
        source_lang: "ru",
        target_lang: "en",
      },
      signal: controller.signal,
    });
  });

  it("rejects an invalid updated-card response", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
      front_text: "hello",
    });

    await expect(
      updateLibraryCard("413b1910-5d07-4c67-93a0-6b8946c59b15", {
        frontText: "hello",
        backText: "привет",
        sourceLang: "en",
        targetLang: "ru",
      }),
    ).rejects.toMatchObject({
      status: 0,
      code: "INVALID_LIBRARY_RESPONSE",
    });
  });
});

describe("deleteLibraryCard", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(undefined);
  });

  it("deletes the exact card route without a trailing slash or request body", async () => {
    const controller = new AbortController();

    await expect(
      deleteLibraryCard("413b1910-5d07-4c67-93a0-6b8946c59b15", controller.signal),
    ).resolves.toBeUndefined();

    expect(apiFetch).toHaveBeenCalledWith("/cards/413b1910-5d07-4c67-93a0-6b8946c59b15", {
      method: "DELETE",
      signal: controller.signal,
    });
  });
});
