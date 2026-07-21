import { ApiError, apiFetch } from "../../../api";
import {
  parseCreatedLibraryCard,
  parseCreatedLibraryDeck,
  parseFavouriteLibraryDeckPage,
  parseLibraryCardPage,
  parseLibraryDeckPage,
  parseUpdatedLibraryCard,
} from "../model/library-contract";
import type {
  CreatedLibraryCard,
  CreatedLibraryDeck,
  CreateLibraryCardInput,
  CreateLibraryDeckInput,
  FavouriteLibraryDeckPage,
  LibraryCardPage,
  LibraryDeckPage,
  LibraryFavouriteResult,
  UpdatedLibraryCard,
  UpdateLibraryCardInput,
} from "../model/library-types";

const LIBRARY_DECKS_PATH = "/bff/decks";
const FAVOURITE_LIBRARY_DECKS_PATH = "/bff/decks/favourite";
const LIBRARY_CARDS_PATH = "/bff/library/cards";

export async function createLibraryDeck(
  input: CreateLibraryDeckInput,
  signal?: AbortSignal,
): Promise<CreatedLibraryDeck> {
  const payload = await apiFetch<unknown>("/decks/", {
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
    query: { cursor },
    signal,
  });

  return parseLibraryDeckPage(payload);
}

export async function getFavouriteLibraryDeckPage(
  cursor: string | null,
  signal?: AbortSignal,
): Promise<FavouriteLibraryDeckPage> {
  const payload = await apiFetch<unknown>(FAVOURITE_LIBRARY_DECKS_PATH, {
    query: { cursor },
    signal,
  });

  return parseFavouriteLibraryDeckPage(payload);
}

export async function getLibraryCardPage(
  cursor: string | null,
  signal?: AbortSignal,
): Promise<LibraryCardPage> {
  const payload = await apiFetch<unknown>(LIBRARY_CARDS_PATH, {
    query: { cursor },
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

  if (updatedCard.uuid !== cardUuid) {
    throw new ApiError({
      status: 0,
      code: "INVALID_LIBRARY_RESPONSE",
      message: "The backend returned an updated card with an unexpected UUID.",
    });
  }

  return updatedCard;
}

export async function deleteLibraryCard(cardUuid: string, signal?: AbortSignal): Promise<void> {
  await apiFetch<void>(`/cards/${cardUuid}`, {
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

  if (
    typeof payload !== "object" ||
    payload === null ||
    !("is_favourite" in payload) ||
    typeof payload.is_favourite !== "boolean"
  ) {
    throw new ApiError({
      status: 0,
      code: "INVALID_FAVOURITE_RESPONSE",
      message: "The backend returned an unexpected favourite value.",
    });
  }

  return { isFavourite: payload.is_favourite };
}
