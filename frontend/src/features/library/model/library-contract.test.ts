import { describe, expect, it } from "vitest";
import { isApiError } from "../../../api";
import {
  parseDeckCardPage,
  parseEditableLibraryDeck,
  parseFavouriteLibraryDeckPage,
  parseLibraryCardPage,
  parseLibraryDeckOptions,
  parseLibraryDeckPage,
} from "./library-contract";

const VALID_RESPONSE = {
  decks: [
    {
      uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
      title: "Daily Words",
      description: null,
      deck_total_words_count: 48,
      user_accuracy: 75,
      is_favourite: true,
      updated_at: "2026-07-17T10:30:00Z",
      cards: [
        {
          uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
          front_text: "hello",
          back_text: "привет",
        },
        {
          uuid: "28dd615b-a6cb-4471-8238-b41c25556bb0",
          front_text: "world",
          back_text: "мир",
        },
      ],
    },
  ],
  next_cursor: "cursor-2",
  has_more: true,
};

const VALID_FAVOURITE_RESPONSE = {
  decks: [
    {
      deck_uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
      owner_uuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
      title: "Daily Words",
      description: null,
      words_count: 48,
      user_accuracy: 91,
      updated_at: "2026-07-17T10:30:00Z",
      is_favourite: true,
      is_following: false,
      cards: [
        {
          uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
          front_text: "hello",
          back_text: "привет",
        },
      ],
    },
  ],
  next_cursor: "favourite-cursor-2",
  has_more: true,
};

const VALID_CARD_RESPONSE = {
  cards: [
    {
      card_uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
      card_owner_uuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
      card_front_text: "hello",
      card_back_text: "привет",
      card_source_lang: "en",
      card_target_lang: "ru",
      card_updated_at: "2026-07-20T09:15:00Z",
    },
  ],
  cursor: "card-cursor-2",
  has_more: true,
};

const VALID_DECK_OPTIONS_RESPONSE = [
  {
    uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
    title: "Daily Words",
    words_count: 48,
  },
  {
    uuid: "f9b7ced5-fbea-4741-82fd-33ea144dab7c",
    title: "Travel Essentials",
    words_count: 0,
  },
];

const VALID_EDITABLE_DECK_RESPONSE = {
  id: 7,
  uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
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

const VALID_DECK_CARD_RESPONSE = {
  id: 17,
  uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
  user_id: 4,
  front_text: "привет",
  back_text: "hello",
  source_lang: "ru",
  target_lang: "en",
  created_at: "2026-07-19T09:15:00Z",
  updated_at: "2026-07-21T18:30:00Z",
};

describe("parseEditableLibraryDeck", () => {
  it("maps the backend deck into editable metadata", () => {
    expect(parseEditableLibraryDeck(VALID_EDITABLE_DECK_RESPONSE)).toEqual({
      uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
      title: "Daily Words",
      description: "Core vocabulary",
      totalWordsCount: 48,
      isPublic: false,
      updatedAt: "2026-07-21T18:30:00Z",
    });
  });

  it("accepts nullable deck metadata", () => {
    expect(
      parseEditableLibraryDeck({
        ...VALID_EDITABLE_DECK_RESPONSE,
        description: null,
        updated_at: null,
      }),
    ).toMatchObject({
      description: null,
      updatedAt: null,
    });
  });

  it.each([
    ["uuid", "not-a-uuid"],
    ["title", null],
    ["description", 42],
    ["words_count", -1],
    ["words_count", 1.5],
    ["is_public", "false"],
    ["updated_at", "not-a-date"],
  ])("rejects malformed %s values", (field, value) => {
    expect(() =>
      parseEditableLibraryDeck({
        ...VALID_EDITABLE_DECK_RESPONSE,
        [field]: value,
      }),
    ).toThrow();
  });
});

describe("parseDeckCardPage", () => {
  it("maps a short page and advances the offset by the returned count", () => {
    expect(parseDeckCardPage([VALID_DECK_CARD_RESPONSE], 50, 50)).toEqual({
      cards: [
        {
          uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
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
  });

  it("reports another page only when the backend returns the full limit", () => {
    expect(
      parseDeckCardPage(
        Array.from({ length: 50 }, () => VALID_DECK_CARD_RESPONSE),
        0,
        50,
      ),
    ).toMatchObject({
      nextOffset: 50,
      hasMore: true,
    });

    expect(parseDeckCardPage([], 100, 50)).toEqual({
      cards: [],
      nextOffset: 100,
      hasMore: false,
    });
  });

  it.each([
    ["uuid", "not-a-uuid"],
    ["front_text", null],
    ["back_text", null],
    ["source_lang", null],
    ["target_lang", null],
    ["updated_at", "not-a-date"],
  ])("rejects malformed card %s values", (field, value) => {
    expect(() =>
      parseDeckCardPage(
        [
          {
            ...VALID_DECK_CARD_RESPONSE,
            [field]: value,
          },
        ],
        0,
        50,
      ),
    ).toThrow();
  });

  it("rejects non-array and over-limit responses", () => {
    expect(() => parseDeckCardPage({ cards: [] }, 0, 50)).toThrow();
    expect(() =>
      parseDeckCardPage(
        Array.from({ length: 51 }, () => VALID_DECK_CARD_RESPONSE),
        0,
        50,
      ),
    ).toThrow();
  });
});

describe("parseLibraryDeckOptions", () => {
  it("maps the short current-user deck list", () => {
    expect(parseLibraryDeckOptions(VALID_DECK_OPTIONS_RESPONSE)).toEqual([
      {
        uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
        title: "Daily Words",
        totalWordsCount: 48,
      },
      {
        uuid: "f9b7ced5-fbea-4741-82fd-33ea144dab7c",
        title: "Travel Essentials",
        totalWordsCount: 0,
      },
    ]);
  });

  it("rejects a non-array response", () => {
    expect(() => parseLibraryDeckOptions({ decks: VALID_DECK_OPTIONS_RESPONSE })).toThrow();
  });

  it.each([
    ["uuid", "not-a-uuid"],
    ["title", null],
    ["words_count", -1],
    ["words_count", 1.5],
  ])("rejects malformed %s values", (field, value) => {
    expect(() =>
      parseLibraryDeckOptions([
        {
          ...VALID_DECK_OPTIONS_RESPONSE[0],
          [field]: value,
        },
      ]),
    ).toThrow();
  });
});

describe("parseLibraryDeckPage", () => {
  it("maps the BFF deck page into the library model", () => {
    expect(parseLibraryDeckPage(VALID_RESPONSE)).toEqual({
      decks: [
        {
          uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
          title: "Daily Words",
          description: null,
          totalWordsCount: 48,
          accuracy: 75,
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
              frontText: "world",
              backText: "мир",
            },
          ],
        },
      ],
      nextCursor: "cursor-2",
      hasMore: true,
    });
  });

  it("rejects malformed deck fields with the library contract code", () => {
    try {
      parseLibraryDeckPage({
        ...VALID_RESPONSE,
        decks: [{ ...VALID_RESPONSE.decks[0], uuid: "not-a-uuid" }],
      });
      expect.fail("Expected parseLibraryDeckPage to throw.");
    } catch (error) {
      expect(isApiError(error)).toBe(true);
      if (isApiError(error)) {
        expect(error.code).toBe("INVALID_LIBRARY_RESPONSE");
        expect(error.status).toBe(0);
      }
    }
  });

  it("accepts an empty card preview and rejects malformed preview cards", () => {
    const emptyPreviewResponse = {
      ...VALID_RESPONSE,
      decks: [{ ...VALID_RESPONSE.decks[0], cards: [] }],
    };

    expect(parseLibraryDeckPage(emptyPreviewResponse).decks[0]?.cards).toEqual([]);
    expect(() =>
      parseLibraryDeckPage({
        ...VALID_RESPONSE,
        decks: [
          {
            ...VALID_RESPONSE.decks[0],
            cards: [{ ...VALID_RESPONSE.decks[0].cards[0], front_text: null }],
          },
        ],
      }),
    ).toThrow();
    expect(() =>
      parseLibraryDeckPage({
        ...VALID_RESPONSE,
        decks: [{ ...VALID_RESPONSE.decks[0], cards: null }],
      }),
    ).toThrow();
  });

  it("rejects pagination metadata that contradicts has_more", () => {
    expect(() =>
      parseLibraryDeckPage({ ...VALID_RESPONSE, next_cursor: null, has_more: true }),
    ).toThrow();
    expect(() =>
      parseLibraryDeckPage({ ...VALID_RESPONSE, next_cursor: "cursor-2", has_more: false }),
    ).toThrow();
  });
});

describe("parseFavouriteLibraryDeckPage", () => {
  it("maps the public DeckWithUserData UUIDs and accuracy", () => {
    expect(parseFavouriteLibraryDeckPage(VALID_FAVOURITE_RESPONSE)).toEqual({
      decks: [
        {
          uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
          ownerUuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
          title: "Daily Words",
          description: null,
          totalWordsCount: 48,
          accuracy: 91,
          updatedAt: "2026-07-17T10:30:00Z",
          isFavourite: true,
          isFollowing: false,
          cards: [
            {
              uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
              frontText: "hello",
              backText: "привет",
            },
          ],
        },
      ],
      nextCursor: "favourite-cursor-2",
      hasMore: true,
    });
  });

  it("accepts omitted optional nullable fields", () => {
    const deck: Partial<(typeof VALID_FAVOURITE_RESPONSE.decks)[number]> = {
      ...VALID_FAVOURITE_RESPONSE.decks[0],
    };
    delete deck.description;
    delete deck.updated_at;

    expect(
      parseFavouriteLibraryDeckPage({
        decks: [deck],
        next_cursor: null,
        has_more: false,
      }),
    ).toEqual({
      decks: [
        {
          uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
          ownerUuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
          title: "Daily Words",
          totalWordsCount: 48,
          accuracy: 91,
          isFavourite: true,
          isFollowing: false,
          cards: [
            {
              uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
              frontText: "hello",
              backText: "привет",
            },
          ],
        },
      ],
      nextCursor: null,
      hasMore: false,
    });
  });

  it.each(["deck_uuid", "owner_uuid"] as const)(
    "rejects a malformed %s with the library contract code",
    (field) => {
      try {
        parseFavouriteLibraryDeckPage({
          ...VALID_FAVOURITE_RESPONSE,
          decks: [{ ...VALID_FAVOURITE_RESPONSE.decks[0], [field]: "not-a-uuid" }],
        });
        expect.fail("Expected parseFavouriteLibraryDeckPage to throw.");
      } catch (error) {
        expect(isApiError(error)).toBe(true);
        if (isApiError(error)) {
          expect(error.code).toBe("INVALID_LIBRARY_RESPONSE");
          expect(error.status).toBe(0);
        }
      }
    },
  );
});

describe("parseLibraryCardPage", () => {
  it("maps the BFF card page and its cursor into the library model", () => {
    expect(parseLibraryCardPage(VALID_CARD_RESPONSE)).toEqual({
      cards: [
        {
          uuid: "413b1910-5d07-4c67-93a0-6b8946c59b15",
          ownerUuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
          frontText: "hello",
          backText: "привет",
          sourceLang: "en",
          targetLang: "ru",
          updatedAt: "2026-07-20T09:15:00Z",
        },
      ],
      nextCursor: "card-cursor-2",
      hasMore: true,
    });
  });

  it.each([
    ["card_uuid", "not-a-uuid"],
    ["card_owner_uuid", "not-an-owner-uuid"],
    ["card_updated_at", "not-a-date"],
    ["card_source_lang", null],
  ])("rejects malformed %s card fields", (field, value) => {
    expect(() =>
      parseLibraryCardPage({
        ...VALID_CARD_RESPONSE,
        cards: [{ ...VALID_CARD_RESPONSE.cards[0], [field]: value }],
      }),
    ).toThrow();
  });

  it("rejects pagination metadata that contradicts has_more", () => {
    expect(() =>
      parseLibraryCardPage({ ...VALID_CARD_RESPONSE, cursor: null, has_more: true }),
    ).toThrow();
    expect(() =>
      parseLibraryCardPage({ ...VALID_CARD_RESPONSE, cursor: "card-cursor-2", has_more: false }),
    ).toThrow();
  });
});
