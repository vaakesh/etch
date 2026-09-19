import { ApiError, apiFetch } from "../../../api";
import { updateLibraryDeckSavedState } from "../../library/model/library-decks-cache";
import {
  parseCatalogDeckPreview,
  parseCatalogDecks,
  parseCatalogPreviewCardPage,
} from "../model/catalog-contract";
import type {
  CatalogDeckPage,
  CatalogDeckPreview,
  CatalogPreviewCardPage,
} from "../model/catalog-types";
import { CATALOG_PREVIEW_CARD_BATCH_SIZE } from "../model/catalog-preview-pagination";

const CATALOG_PATH = "/bff/catalog";
export const CATALOG_PAGE_SIZE = 30;
export const CATALOG_SEARCH_MAX_LENGTH = 50;

function assertExpectedUuid(expectedUuid: string, actualUuid: string): void {
  if (actualUuid !== expectedUuid) {
    throw new ApiError({
      status: 0,
      code: "INVALID_CATALOG_RESPONSE",
      message: "The backend returned a deck with an unexpected UUID.",
    });
  }
}

export async function getCatalogDeckPage(
  page: number,
  searchQuery: string | null,
  signal?: AbortSignal,
): Promise<CatalogDeckPage> {
  const payload = await apiFetch<unknown>(CATALOG_PATH, {
    query: {
      page,
      limit: CATALOG_PAGE_SIZE,
      ...(searchQuery === null ? {} : { q: searchQuery.trim() }),
    },
    signal,
  });
  const decks = parseCatalogDecks(payload);

  return {
    decks,
    page,
    hasMore: decks.length === CATALOG_PAGE_SIZE,
  };
}

export async function setCatalogDeckSaved(
  deckUuid: string,
  isSaved: boolean,
  signal?: AbortSignal,
): Promise<void> {
  await apiFetch<void>(`/decks/${deckUuid}/${isSaved ? "save" : "unsave"}`, {
    method: "POST",
    signal,
  });

  updateLibraryDeckSavedState(deckUuid, isSaved);
}

export async function getCatalogDeckPreview(
  deckUuid: string,
  signal?: AbortSignal,
): Promise<CatalogDeckPreview> {
  const payload = await apiFetch<unknown>(`/decks/${deckUuid}`, { signal });
  const deck = parseCatalogDeckPreview(payload);

  assertExpectedUuid(deckUuid, deck.uuid);
  return deck;
}

export async function getCatalogPreviewCardPage(
  deckUuid: string,
  offset: number,
  signal?: AbortSignal,
): Promise<CatalogPreviewCardPage> {
  const payload = await apiFetch<unknown>(`/decks/${deckUuid}/cards`, {
    query: { offset, limit: CATALOG_PREVIEW_CARD_BATCH_SIZE },
    signal,
  });

  return parseCatalogPreviewCardPage(payload, offset, CATALOG_PREVIEW_CARD_BATCH_SIZE);
}

export async function getCatalogDeckPreviewInitialData(
  deckUuid: string,
  signal?: AbortSignal,
): Promise<{ deck: CatalogDeckPreview; cardPage: CatalogPreviewCardPage }> {
  const [deck, cardPage] = await Promise.all([
    getCatalogDeckPreview(deckUuid, signal),
    getCatalogPreviewCardPage(deckUuid, 0, signal),
  ]);

  return { deck, cardPage };
}
