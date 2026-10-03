import { ApiError, apiFetch } from "../../../api";
import {
  parseArchiveCards,
  parseArchivedDeck,
  parseArchiveOffers,
  parsePreservedArchive,
} from "../model/archive-contract";
import type {
  ArchiveCard,
  ArchivedDeck,
  ArchiveOffer,
  PreservedArchive,
} from "../model/archive-types";

export const ARCHIVE_CARD_BATCH_SIZE = 50;

export async function preserveArchivedDeck(
  deckUuid: string,
  signal?: AbortSignal,
): Promise<PreservedArchive> {
  const payload = await apiFetch<unknown>(`/decks/${deckUuid}/preserve`, {
    method: "POST",
    signal,
  });
  return parsePreservedArchive(payload);
}

export async function getArchiveOffers(signal?: AbortSignal): Promise<ArchiveOffer[]> {
  return parseArchiveOffers(await apiFetch<unknown>("/decks/archives", { signal }));
}

export async function getArchivedDeck(
  deckUuid: string,
  signal?: AbortSignal,
): Promise<ArchivedDeck> {
  const deck = parseArchivedDeck(
    await apiFetch<unknown>(`/decks/archives/${deckUuid}`, { signal }),
  );
  if (deck.uuid !== deckUuid) {
    throw new ApiError({
      status: 0,
      code: "INVALID_ARCHIVE_RESPONSE",
      message: "The backend returned an unexpected archive UUID.",
    });
  }
  return deck;
}

export async function getArchiveCards(
  deckUuid: string,
  offset: number,
  signal?: AbortSignal,
): Promise<ArchiveCard[]> {
  const payload = await apiFetch<unknown>(`/decks/archives/${deckUuid}/cards`, {
    query: { offset, limit: ARCHIVE_CARD_BATCH_SIZE },
    signal,
  });
  return parseArchiveCards(payload, ARCHIVE_CARD_BATCH_SIZE);
}
