import {
  createSessionCacheKey,
  deleteSessionCacheEntry,
  getCurrentSessionCacheScope,
  getSessionCacheEntry,
  setSessionCacheEntry,
  type SessionCacheScope,
} from "../../../auth/model/session-cache";
import { subscribeToLibraryDeckSaveChanges } from "../../library/model/library-decks-cache";
import type { CatalogDeckPage } from "./catalog-types";

interface CachedCatalogDeckPage {
  searchQuery: string;
  page: CatalogDeckPage;
}

const CATALOG_DECK_PAGE_CACHE_KEY = createSessionCacheKey<CachedCatalogDeckPage>("catalog.decks");

export function getCachedCatalogDeckPage(
  scope: SessionCacheScope | null,
  searchQuery: string,
  page: number,
): CatalogDeckPage | null {
  const cached = getSessionCacheEntry(scope, CATALOG_DECK_PAGE_CACHE_KEY);
  return cached?.searchQuery === searchQuery && cached.page.page === page ? cached.page : null;
}

export function setCachedCatalogDeckPage(
  scope: SessionCacheScope | null,
  searchQuery: string,
  page: CatalogDeckPage,
): void {
  setSessionCacheEntry(scope, CATALOG_DECK_PAGE_CACHE_KEY, { searchQuery, page });
}

export function clearCachedCatalogDeckPage(scope: SessionCacheScope | null): void {
  deleteSessionCacheEntry(scope, CATALOG_DECK_PAGE_CACHE_KEY);
}

subscribeToLibraryDeckSaveChanges(() => {
  clearCachedCatalogDeckPage(getCurrentSessionCacheScope());
});
