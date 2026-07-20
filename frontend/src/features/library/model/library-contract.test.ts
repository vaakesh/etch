import { describe, expect, it } from "vitest";
import { isApiError } from "../../../api";
import { parseLibraryDeckPage } from "./library-contract";

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
