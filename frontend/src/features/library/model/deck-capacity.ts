import { API_ERROR_CODES, hasApiErrorCode } from "../../../api";

export const MAX_DECK_SIZE = 5000;

/** Backend отвечает 409 и на «карточка уже в колоде», и на превышение лимита колоды. */
export function isDeckSizeLimitError(error: unknown): boolean {
  return hasApiErrorCode(error, API_ERROR_CODES.deckSizeLimitExceeded);
}

export function getDeckFreeSlots(deckWordsCount: number): number {
  return Math.max(MAX_DECK_SIZE - deckWordsCount, 0);
}

export function fitsIntoDeck(deckWordsCount: number, addedCardsCount: number): boolean {
  return deckWordsCount + addedCardsCount <= MAX_DECK_SIZE;
}
