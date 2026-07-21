import { describe, expect, it } from "vitest";
import { isApiError } from "../../../api";
import {
  parseFavouriteLibraryDeckPage,
  parseLibraryCardPage,
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
