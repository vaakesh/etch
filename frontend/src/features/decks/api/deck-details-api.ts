import { ApiError, apiFetch } from "../../../api";
import {
  parseDeckDetails,
  parseDeckDetailsCardBatch,
  parseDeckDetailsCardResponse,
} from "../model/deck-details-contract";
import { DECK_DETAILS_CARD_BATCH_SIZE } from "../model/deck-details-pagination";
import type {
  DeckDetails,
  DeckDetailsCard,
  DeckDetailsCardBatch,
  UpdateDeckDetailsCardInput,
} from "../model/deck-details-types";

function assertExpectedUuid(expectedUuid: string, actualUuid: string, resource: string): void {
  if (actualUuid !== expectedUuid) {
    throw new ApiError({
      status: 0,
      code: "INVALID_DECK_DETAILS_RESPONSE",
      message: `The backend returned ${resource} with an unexpected UUID.`,
    });
  }
}

export async function getDeckDetails(deckUuid: string, signal?: AbortSignal): Promise<DeckDetails> {
  const payload = await apiFetch<unknown>(`/decks/${deckUuid}`, { signal });
  const deck = parseDeckDetails(payload);

  assertExpectedUuid(deckUuid, deck.uuid, "a deck");
  return deck;
}

export async function getDeckDetailsCardBatch(
  deckUuid: string,
  offset: number,
  signal?: AbortSignal,
): Promise<DeckDetailsCardBatch> {
  const payload = await apiFetch<unknown>(`/decks/${deckUuid}/cards`, {
    query: { offset, limit: DECK_DETAILS_CARD_BATCH_SIZE },
    signal,
  });

  return parseDeckDetailsCardBatch(payload, offset, DECK_DETAILS_CARD_BATCH_SIZE);
}

export async function getDeckDetailsInitialData(
  deckUuid: string,
  signal?: AbortSignal,
): Promise<{ deck: DeckDetails; cardBatch: DeckDetailsCardBatch }> {
  const [deck, cardBatch] = await Promise.all([
    getDeckDetails(deckUuid, signal),
    getDeckDetailsCardBatch(deckUuid, 0, signal),
  ]);

  return { deck, cardBatch };
}

export async function updateDeckDetailsCard(
  cardUuid: string,
  input: UpdateDeckDetailsCardInput,
  signal?: AbortSignal,
): Promise<DeckDetailsCard> {
  const payload = await apiFetch<unknown>(`/cards/${cardUuid}`, {
    method: "PATCH",
    body: {
      front_text: input.frontText,
      back_text: input.backText,
      front_lang: input.frontLang,
      back_lang: input.backLang,
    },
    signal,
  });
  const card = parseDeckDetailsCardResponse(payload);

  assertExpectedUuid(cardUuid, card.uuid, "a card");
  return card;
}

export async function deleteDeckDetailsCard(cardUuid: string, signal?: AbortSignal): Promise<void> {
  await apiFetch<void>(`/cards/${cardUuid}`, { method: "DELETE", signal });
}

export async function deleteDeckFromDetails(deckUuid: string, signal?: AbortSignal): Promise<void> {
  await apiFetch<void>(`/decks/${deckUuid}`, { method: "DELETE", signal });
}
