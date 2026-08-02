import { describe, expect, it } from "vitest";
import { isApiError } from "../../../api";
import {
  parseDeckCardPage,
  parseEditableLibraryDeck,
  parseLibraryCardPage,
  parseLibraryDeckOptionPage,
  parseLibraryDeckPage,
} from "./library-contract";

const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const OWNER_UUID = "d2f61c35-11d0-489e-837d-3845418ba39e";
const CARD_UUID = "413b1910-5d07-4c67-93a0-6b8946c59b15";

const VALID_CARD_DETAIL = {
  uuid: CARD_UUID,
  front_text: "привет",
  back_text: "hello",
  source_lang: "ru",
  target_lang: "en",
};

const VALID_DECK_DETAIL = {
  uuid: DECK_UUID,
  title: "Daily Words",
  description: "Core vocabulary",
  words_count: 48,
  is_public: false,
  updated_at: "2026-07-21T18:30:00Z",
};

const VALID_LIBRARY_CARD = {
  card_uuid: CARD_UUID,
  front_text: "hello",
  back_text: "привет",
  source_lang: "en",
  target_lang: "ru",
  updated_at: "2026-07-20T09:15:00Z",
};

const VALID_DECK_PAGE = {
  items: [
    {
      deck_uuid: DECK_UUID,
      owner_uuid: OWNER_UUID,
      title: "Daily Words",
      description: null,
      deck_words_count: 48,
      user_accuracy: 75,
      is_favourite: true,
      updated_at: "2026-07-17T10:30:00Z",
      cards: [VALID_LIBRARY_CARD],
    },
  ],
  next_cursor: "cursor-2",
  has_more: true,
};

const VALID_CARD_PAGE = {
  items: [VALID_LIBRARY_CARD],
  next_cursor: "card-cursor-2",
  has_more: true,
};

describe("parseEditableLibraryDeck", () => {
  it("maps DeckDetail into editable metadata", () => {
    expect(parseEditableLibraryDeck(VALID_DECK_DETAIL)).toEqual({
      uuid: DECK_UUID,
      title: "Daily Words",
      description: "Core vocabulary",
      totalWordsCount: 48,
      isPublic: false,
      updatedAt: "2026-07-21T18:30:00Z",
    });
  });

  it("accepts nullable metadata and rejects malformed fields", () => {
    expect(
      parseEditableLibraryDeck({
        ...VALID_DECK_DETAIL,
        description: null,
        updated_at: null,
      }),
    ).toMatchObject({ description: null, updatedAt: null });

    expect(() => parseEditableLibraryDeck({ ...VALID_DECK_DETAIL, words_count: -1 })).toThrow();
    expect(() => parseEditableLibraryDeck({ ...VALID_DECK_DETAIL, uuid: "not-a-uuid" })).toThrow();
  });
});

describe("parseDeckCardPage", () => {
  it("maps CardDetail and derives offset pagination from the array length", () => {
    expect(parseDeckCardPage([VALID_CARD_DETAIL], 50, 50)).toEqual({
      cards: [
        {
          uuid: CARD_UUID,
          frontText: "привет",
          backText: "hello",
          sourceLang: "ru",
          targetLang: "en",
        },
      ],
      nextOffset: 51,
      hasMore: false,
    });

    expect(
      parseDeckCardPage(
        Array.from({ length: 50 }, () => VALID_CARD_DETAIL),
        0,
        50,
      ),
    ).toMatchObject({ nextOffset: 50, hasMore: true });
  });

  it("rejects the removed updated_at requirement and malformed responses", () => {
    expect(parseDeckCardPage([VALID_CARD_DETAIL], 0, 50).cards[0]).not.toHaveProperty("updatedAt");
    expect(() => parseDeckCardPage({ items: [] }, 0, 50)).toThrow();
    expect(() =>
      parseDeckCardPage(
        Array.from({ length: 51 }, () => VALID_CARD_DETAIL),
        0,
        50,
      ),
    ).toThrow();
  });
});

describe("parseLibraryDeckOptionPage", () => {
  it("maps the new CursorPage[DeckDetail] response", () => {
    expect(
      parseLibraryDeckOptionPage({
        items: [VALID_DECK_DETAIL],
        next_cursor: null,
        has_more: false,
      }),
    ).toEqual({
      decks: [{ uuid: DECK_UUID, title: "Daily Words", totalWordsCount: 48 }],
      nextCursor: null,
      hasMore: false,
    });
  });

  it("rejects the previous bare-array response", () => {
    expect(() => parseLibraryDeckOptionPage([VALID_DECK_DETAIL])).toThrow();
  });
});

describe("parseLibraryDeckPage", () => {
  it("maps CursorPage[DeckLibraryPage] for both normal and favourite requests", () => {
    expect(parseLibraryDeckPage(VALID_DECK_PAGE)).toEqual({
      decks: [
        {
          uuid: DECK_UUID,
          ownerUuid: OWNER_UUID,
          title: "Daily Words",
          description: null,
          totalWordsCount: 48,
          accuracy: 75,
          isFavourite: true,
          updatedAt: "2026-07-17T10:30:00Z",
          cards: [
            {
              uuid: CARD_UUID,
              frontText: "hello",
              backText: "привет",
              sourceLang: "en",
              targetLang: "ru",
              updatedAt: "2026-07-20T09:15:00Z",
            },
          ],
        },
      ],
      nextCursor: "cursor-2",
      hasMore: true,
    });
  });

  it("reports a contract error for the removed deck field names", () => {
    try {
      parseLibraryDeckPage({
        ...VALID_DECK_PAGE,
        items: [
          {
            ...VALID_DECK_PAGE.items[0],
            deck_uuid: undefined,
            uuid: DECK_UUID,
          },
        ],
      });
      expect.fail("Expected parseLibraryDeckPage to throw.");
    } catch (error) {
      expect(isApiError(error)).toBe(true);
      if (isApiError(error)) {
        expect(error).toMatchObject({ status: 0, code: "INVALID_LIBRARY_RESPONSE" });
      }
    }
  });

  it("validates card previews and cursor invariants", () => {
    expect(() =>
      parseLibraryDeckPage({
        ...VALID_DECK_PAGE,
        items: [
          {
            ...VALID_DECK_PAGE.items[0],
            cards: [{ ...VALID_LIBRARY_CARD, card_uuid: "not-a-uuid" }],
          },
        ],
      }),
    ).toThrow();
    expect(() =>
      parseLibraryDeckPage({ ...VALID_DECK_PAGE, next_cursor: null, has_more: true }),
    ).toThrow();
    expect(() =>
      parseLibraryDeckPage({ ...VALID_DECK_PAGE, next_cursor: "cursor", has_more: false }),
    ).toThrow();
  });
});

describe("parseLibraryCardPage", () => {
  it("maps CursorPage[CardLibraryPage] without the removed owner field", () => {
    expect(parseLibraryCardPage(VALID_CARD_PAGE)).toEqual({
      cards: [
        {
          uuid: CARD_UUID,
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

  it("rejects old response keys, malformed fields, and inconsistent pagination", () => {
    expect(() =>
      parseLibraryCardPage({
        cards: VALID_CARD_PAGE.items,
        cursor: null,
        has_more: false,
      }),
    ).toThrow();
    expect(() =>
      parseLibraryCardPage({
        ...VALID_CARD_PAGE,
        items: [{ ...VALID_LIBRARY_CARD, updated_at: "not-a-date" }],
      }),
    ).toThrow();
    expect(() =>
      parseLibraryCardPage({ ...VALID_CARD_PAGE, next_cursor: null, has_more: true }),
    ).toThrow();
  });
});
