import { ApiError, apiFetch } from "../../../api";
import { parseFavouriteLibraryDeckPage, parseLibraryDeckPage } from "../model/library-contract";
import type {
  FavouriteLibraryDeckPage,
  LibraryDeckPage,
  LibraryFavouriteResult,
} from "../model/library-types";

const LIBRARY_DECKS_PATH = "/bff/decks";
const FAVOURITE_LIBRARY_DECKS_PATH = "/bff/decks/favourite";

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
