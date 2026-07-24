import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch } from "../../../api";
import {
  addLibraryCardToDeck,
  createLibraryCard,
  createLibraryDeck,
  deleteLibraryCard,
  getEditableLibraryDeck,
  getFavouriteLibraryDeckPage,
  getLibraryCardPage,
  getLibraryDeckCardPage,
  getLibraryDeckOptions,
  getLibraryDeckPage,
  removeLibraryCardFromDeck,
  setLibraryDeckFavourite,
  updateEditableLibraryDeck,
  updateLibraryCard,
} from "./library-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const RESPONSE = { decks: [], next_cursor: null, has_more: false };
const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const CARD_UUID = "413b1910-5d07-4c67-93a0-6b8946c59b15";
const EDITABLE_DECK_RESPONSE = {
  id: 7,
  uuid: DECK_UUID,
  user_id: 4,
  source_deck_id: null,
  title: "Daily Words",
  description: "Core vocabulary",
  words_count: 48,
  is_public: false,
  version: 2,
  created_at: "2026-07-19T09:15:00Z",
  updated_at: "2026-07-21T18:30:00Z",
};
const DECK_CARD_RESPONSE = {
  id: 17,
  uuid: CARD_UUID,
  user_id: 4,
  front_text: "привет",
  back_text: "hello",
  source_lang: "ru",
  target_lang: "en",
  created_at: "2026-07-19T09:15:00Z",
  updated_at: "2026-07-21T18:30:00Z",
};

describe("getEditableLibraryDeck", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(EDITABLE_DECK_RESPONSE);
  });

  it("loads the exact deck route and maps the editable fields", async () => {
    const controller = new AbortController();

    await expect(getEditableLibraryDeck(DECK_UUID, controller.signal)).resolves.toEqual({
      uuid: DECK_UUID,
      title: "Daily Words",
      description: "Core vocabulary",
      totalWordsCount: 48,
      isPublic: false,
      updatedAt: "2026-07-21T18:30:00Z",
    });

    expect(apiFetch).toHaveBeenCalledWith(`/decks/${DECK_UUID}`, {
      signal: controller.signal,
    });
  });

  it("rejects a deck response for a different UUID", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ...EDITABLE_DECK_RESPONSE,
      uuid: "f9b7ced5-fbea-4741-82fd-33ea144dab7c",
    });

    await expect(getEditableLibraryDeck(DECK_UUID)).rejects.toMatchObject({
      status: 0,
      code: "INVALID_LIBRARY_RESPONSE",
    });
  });
});

describe("updateEditableLibraryDeck", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue({
      ...EDITABLE_DECK_RESPONSE,
      title: "Daily phrases",
      description: null,
      updated_at: "2026-07-22T10:45:00Z",
    });
  });

  it("patches only title and description on the exact deck route", async () => {
    const controller = new AbortController();

    await expect(
      updateEditableLibraryDeck(
        DECK_UUID,
        { title: "Daily phrases", description: null },
        controller.signal,
      ),
    ).resolves.toEqual({
      uuid: DECK_UUID,
      title: "Daily phrases",
      description: null,
      totalWordsCount: 48,
      isPublic: false,
      updatedAt: "2026-07-22T10:45:00Z",
    });

    expect(apiFetch).toHaveBeenCalledWith(`/decks/${DECK_UUID}`, {
      method: "PATCH",
      body: {
        title: "Daily phrases",
        description: null,
      },
      signal: controller.signal,
    });
  });

  it("rejects an updated deck response for a different UUID", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ...EDITABLE_DECK_RESPONSE,
      uuid: "f9b7ced5-fbea-4741-82fd-33ea144dab7c",
    });

    await expect(
      updateEditableLibraryDeck(DECK_UUID, {
        title: "Daily phrases",
        description: null,
      }),
    ).rejects.toMatchObject({
      status: 0,
      code: "INVALID_LIBRARY_RESPONSE",
    });
  });
});

describe("getLibraryDeckCardPage", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue([DECK_CARD_RESPONSE]);
  });

  it("loads the next deck-card page with the fixed limit of 50", async () => {
    const controller = new AbortController();

    await expect(getLibraryDeckCardPage(DECK_UUID, 50, controller.signal)).resolves.toEqual({
      cards: [
        {
          uuid: CARD_UUID,
          frontText: "привет",
          backText: "hello",
          sourceLang: "ru",
          targetLang: "en",
          updatedAt: "2026-07-21T18:30:00Z",
        },
      ],
      nextOffset: 51,
      hasMore: false,
    });

    expect(apiFetch).toHaveBeenCalledWith(`/decks/${DECK_UUID}/cards`, {
      query: { offset: 50, limit: 50 },
      signal: controller.signal,
    });
  });
});

describe("removeLibraryCardFromDeck", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(null);
  });

  it("posts the exact remove route without deleting the card itself", async () => {
    const controller = new AbortController();

    await expect(
      removeLibraryCardFromDeck(DECK_UUID, CARD_UUID, controller.signal),
    ).resolves.toBeUndefined();

    expect(apiFetch).toHaveBeenCalledWith(`/decks/${DECK_UUID}/cards/remove/${CARD_UUID}`, {
      method: "POST",
      signal: controller.signal,
    });
  });
});

describe("getLibraryDeckOptions", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue([
      {
        uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
        title: "Daily Words",
        words_count: 48,
      },
    ]);
  });

  it("loads and maps the exact current-user deck route", async () => {
    const controller = new AbortController();

    await expect(getLibraryDeckOptions(controller.signal)).resolves.toEqual([
      {
        uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
        title: "Daily Words",
        totalWordsCount: 48,
      },
    ]);

    expect(apiFetch).toHaveBeenCalledWith("/users/me/decks", {
      signal: controller.signal,
    });
  });
});

describe("addLibraryCardToDeck", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("posts the exact deck-card route without a body", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ uuid: "77e51a47-5c34-48cc-825e-c04a0a2998d8" });
    const controller = new AbortController();

    await expect(
      addLibraryCardToDeck(
        "714d882d-726e-4dcb-9303-a8bf4638429c",
        "413b1910-5d07-4c67-93a0-6b8946c59b15",
        controller.signal,
      ),
    ).resolves.toBe("added");

    expect(apiFetch).toHaveBeenCalledWith(
      "/decks/714d882d-726e-4dcb-9303-a8bf4638429c/cards/413b1910-5d07-4c67-93a0-6b8946c59b15",
      {
        method: "POST",
        signal: controller.signal,
      },
    );
  });

  it("treats a 409 response as an already-present card", async () => {
    vi.mocked(apiFetch).mockRejectedValue(
      new ApiError({ status: 409, message: "Card already exists in this deck" }),
    );

    await expect(
      addLibraryCardToDeck(
        "714d882d-726e-4dcb-9303-a8bf4638429c",
        "413b1910-5d07-4c67-93a0-6b8946c59b15",
      ),
    ).resolves.toBe("already-present");
  });

  it("rethrows non-409 errors", async () => {
    const error = new ApiError({ status: 403, message: "Permission denied" });
    vi.mocked(apiFetch).mockRejectedValue(error);

    await expect(
      addLibraryCardToDeck(
        "714d882d-726e-4dcb-9303-a8bf4638429c",
        "413b1910-5d07-4c67-93a0-6b8946c59b15",
      ),
    ).rejects.toBe(error);
  });
});

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
