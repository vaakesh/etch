import type { DeckDetailsCard } from "./deck-details-types";

export const DECK_DETAILS_CARD_BATCH_SIZE = 300;
export const DECK_DETAILS_CARD_PAGE_SIZE = 50;

const PAGES_PER_BATCH = DECK_DETAILS_CARD_BATCH_SIZE / DECK_DETAILS_CARD_PAGE_SIZE;

export function getDeckDetailsPageCount(totalCardsCount: number): number {
  return Math.ceil(Math.max(0, totalCardsCount) / DECK_DETAILS_CARD_PAGE_SIZE);
}

export function getDeckDetailsBatchOffset(page: number): number {
  const safePage = Math.max(1, Math.floor(page));
  return Math.floor((safePage - 1) / PAGES_PER_BATCH) * DECK_DETAILS_CARD_BATCH_SIZE;
}

export function getDeckDetailsCardsForPage(
  cards: readonly DeckDetailsCard[],
  batchOffset: number,
  page: number,
): readonly DeckDetailsCard[] {
  const pageOffset = (Math.max(1, Math.floor(page)) - 1) * DECK_DETAILS_CARD_PAGE_SIZE;
  const startIndex = pageOffset - batchOffset;

  if (startIndex < 0 || startIndex >= cards.length) {
    return [];
  }

  return cards.slice(startIndex, startIndex + DECK_DETAILS_CARD_PAGE_SIZE);
}
