import { describe, expect, it } from "vitest";
import type { DeckDetailsCard } from "./deck-details-types";
import {
  DECK_DETAILS_CARD_PAGE_SIZE,
  getDeckDetailsBatchOffset,
  getDeckDetailsCardsForPage,
  getDeckDetailsPageCount,
} from "./deck-details-pagination";

function createCards(count: number): readonly DeckDetailsCard[] {
  return Array.from({ length: count }, (_, index) => ({
    uuid: `card-${index + 1}`,
    frontText: `Front ${index + 1}`,
    backText: `Back ${index + 1}`,
    frontLang: "en",
    backLang: "ru",
    updatedAt: "2026-09-10T10:00:00Z",
  }));
}

describe("deck-details pagination", () => {
  it.each([
    [1, 0],
    [6, 0],
    [7, 300],
    [12, 300],
    [13, 600],
  ])("maps page %s to batch offset %s", (page, expectedOffset) => {
    expect(getDeckDetailsBatchOffset(page)).toBe(expectedOffset);
  });

  it("splits one batch into six pages of 50 cards", () => {
    const cards = createCards(300);

    expect(getDeckDetailsCardsForPage(cards, 0, 1)).toHaveLength(DECK_DETAILS_CARD_PAGE_SIZE);
    expect(getDeckDetailsCardsForPage(cards, 0, 6).map((card) => card.uuid)).toEqual(
      Array.from({ length: 50 }, (_, index) => `card-${index + 251}`),
    );
  });

  it.each([
    [0, 0],
    [1, 1],
    [50, 1],
    [51, 2],
    [300, 6],
    [301, 7],
  ])("maps %s cards to %s pages", (totalCardsCount, expectedPageCount) => {
    expect(getDeckDetailsPageCount(totalCardsCount)).toBe(expectedPageCount);
  });
});
