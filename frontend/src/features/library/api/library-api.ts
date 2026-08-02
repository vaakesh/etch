import { ApiError, apiFetch, isApiError } from "../../../api";
import {
  parseCreatedLibraryCard,
  parseCreatedLibraryDeck,
  parseDeckCardPage,
  parseEditableLibraryDeck,
  parseLibraryCardPage,
  parseLibraryDeckOptionPage,
  parseLibraryDeckPage,
  parseUpdatedLibraryCard,
} from "../model/library-contract";
import type {
  CreatedLibraryCard,
  CreatedLibraryDeck,
  CreateLibraryCardInput,
  CreateLibraryDeckInput,
  DeckCardPage,
  EditableLibraryDeck,
  LibraryCardDeckAddStatus,
  LibraryCardPage,
  LibraryDeckOption,
  LibraryDeckPage,
  LibraryFavouriteResult,
  UpdatedLibraryCard,
  UpdateLibraryCardInput,
  UpdateLibraryDeckInput,
} from "../model/library-types";

const LIBRARY_DECKS_PATH = "/bff/library/decks";
const LIBRARY_CARDS_PATH = "/bff/library/cards";
export const DECK_CARD_PAGE_SIZE = 50;
const LIBRARY_PAGE_SIZE = 50;
const DECK_OPTIONS_PAGE_SIZE = 100;

function assertExpectedUuid(expectedUuid: string, actualUuid: string, resource: string): void {
  if (actualUuid !== expectedUuid) {
    throw new ApiError({
      status: 0,
      code: "INVALID_LIBRARY_RESPONSE",
      message: `The backend returned ${resource} with an unexpected UUID.`,
    });
  }
}

export async function getEditableLibraryDeck(
  deckUuid: string,
  signal?: AbortSignal,
): Promise<EditableLibraryDeck> {
  const payload = await apiFetch<unknown>(`/decks/${deckUuid}`, { signal });
  const deck = parseEditableLibraryDeck(payload);

  assertExpectedUuid(deckUuid, deck.uuid, "a deck");
  return deck;
}

export async function updateEditableLibraryDeck(
  deckUuid: string,
  input: UpdateLibraryDeckInput,
  signal?: AbortSignal,
): Promise<EditableLibraryDeck> {
  const payload = await apiFetch<unknown>(`/decks/${deckUuid}`, {
    method: "PATCH",
    body: {
      title: input.title,
      description: input.description,
      is_public: input.isPublic,
    },
    signal,
  });
  const deck = parseEditableLibraryDeck(payload);

  assertExpectedUuid(deckUuid, deck.uuid, "an updated deck");
  return deck;
}

export async function getLibraryDeckCardPage(
  deckUuid: string,
  offset: number,
  signal?: AbortSignal,
): Promise<DeckCardPage> {
  const payload = await apiFetch<unknown>(`/decks/${deckUuid}/cards`, {
    query: { offset, limit: DECK_CARD_PAGE_SIZE },
    signal,
  });

  return parseDeckCardPage(payload, offset, DECK_CARD_PAGE_SIZE);
}

export async function removeLibraryCardFromDeck(
  deckUuid: string,
  cardUuid: string,
  signal?: AbortSignal,
): Promise<void> {
  await apiFetch<void>(`/decks/${deckUuid}/cards/remove/${cardUuid}`, {
    method: "POST",
    signal,
  });
}

export async function getLibraryDeckOptions(
  signal?: AbortSignal,
): Promise<readonly LibraryDeckOption[]> {
  const decks: LibraryDeckOption[] = [];
  const knownDeckUuids = new Set<string>();
  const requestedCursors = new Set<string | null>();
  let cursor: string | null = null;

  do {
    if (requestedCursors.has(cursor)) {
      throw new ApiError({
        status: 0,
        code: "INVALID_LIBRARY_RESPONSE",
        message: "The backend repeated a deck-options pagination cursor.",
      });
    }
    requestedCursors.add(cursor);

    const payload = await apiFetch<unknown>("/users/me/decks", {
      query: { cursor, limit: DECK_OPTIONS_PAGE_SIZE },
      signal,
    });
    const page = parseLibraryDeckOptionPage(payload);

    page.decks.forEach((deck) => {
      if (!knownDeckUuids.has(deck.uuid)) {
        knownDeckUuids.add(deck.uuid);
        decks.push(deck);
      }
    });
    cursor = page.hasMore ? page.nextCursor : null;
  } while (cursor !== null);

  return decks;
}

export async function addLibraryCardToDeck(
  deckUuid: string,
  cardUuid: string,
  signal?: AbortSignal,
): Promise<LibraryCardDeckAddStatus> {
  try {
    await apiFetch<unknown>(`/decks/${deckUuid}/cards/${cardUuid}`, {
      method: "POST",
      signal,
    });
    return "added";
  } catch (error: unknown) {
    if (isApiError(error) && error.status === 409) {
      return "already-present";
    }

    throw error;
  }
}

export async function createLibraryDeck(
  input: CreateLibraryDeckInput,
  signal?: AbortSignal,
): Promise<CreatedLibraryDeck> {
  const payload = await apiFetch<unknown>("/decks/create", {
    method: "POST",
    body: {
      title: input.title,
      description: input.description,
      is_public: input.isPublic,
    },
    signal,
  });

  return parseCreatedLibraryDeck(payload);
}

export async function createLibraryCard(
  input: CreateLibraryCardInput,
  signal?: AbortSignal,
): Promise<CreatedLibraryCard> {
  const payload = await apiFetch<unknown>("/cards/", {
    method: "POST",
    body: {
      front_text: input.frontText,
      back_text: input.backText,
      source_lang: input.sourceLang,
      target_lang: input.targetLang,
    },
    signal,
  });

  return parseCreatedLibraryCard(payload);
}

export async function getLibraryDeckPage(
  cursor: string | null,
  signal?: AbortSignal,
): Promise<LibraryDeckPage> {
  const payload = await apiFetch<unknown>(LIBRARY_DECKS_PATH, {
    query: { cursor, is_favourite: false, limit: LIBRARY_PAGE_SIZE },
    signal,
  });

  return parseLibraryDeckPage(payload);
}

export async function getFavouriteLibraryDeckPage(
  cursor: string | null,
  signal?: AbortSignal,
): Promise<LibraryDeckPage> {
  const payload = await apiFetch<unknown>(LIBRARY_DECKS_PATH, {
    query: { cursor, is_favourite: true, limit: LIBRARY_PAGE_SIZE },
    signal,
  });

  return parseLibraryDeckPage(payload);
}

export async function getLibraryCardPage(
  cursor: string | null,
  signal?: AbortSignal,
): Promise<LibraryCardPage> {
  const payload = await apiFetch<unknown>(LIBRARY_CARDS_PATH, {
    query: { cursor, limit: LIBRARY_PAGE_SIZE },
    signal,
  });

  return parseLibraryCardPage(payload);
}

export async function updateLibraryCard(
  cardUuid: string,
  input: UpdateLibraryCardInput,
  signal?: AbortSignal,
): Promise<UpdatedLibraryCard> {
  const payload = await apiFetch<unknown>(`/cards/${cardUuid}`, {
    method: "PATCH",
    body: {
      front_text: input.frontText,
      back_text: input.backText,
      source_lang: input.sourceLang,
      target_lang: input.targetLang,
    },
    signal,
  });

  const updatedCard = parseUpdatedLibraryCard(payload);

  assertExpectedUuid(cardUuid, updatedCard.uuid, "an updated card");

  return updatedCard;
}

export async function deleteLibraryCard(cardUuid: string, signal?: AbortSignal): Promise<void> {
  await apiFetch<void>(`/cards/${cardUuid}`, {
    method: "DELETE",
    signal,
  });
}

export async function deleteLibraryDeck(deckUuid: string, signal?: AbortSignal): Promise<void> {
  await apiFetch<void>(`/decks/${deckUuid}`, {
    method: "DELETE",
    signal,
  });
}

export async function setLibraryDeckFavourite(
  deckUuid: string,
  value: boolean,
  signal?: AbortSignal,
): Promise<LibraryFavouriteResult> {
  const payload = await apiFetch<unknown>(`/decks/${deckUuid}/set-favourite`, {
    method: "PATCH",
    query: { value },
    signal,
  });

  if (typeof payload !== "boolean") {
    throw new ApiError({
      status: 0,
      code: "INVALID_FAVOURITE_RESPONSE",
      message: "The backend returned an unexpected favourite value.",
    });
  }

  return { isFavourite: payload };
}
