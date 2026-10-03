import {
  createSessionCacheKey,
  deleteSessionCacheEntry,
  getCurrentSessionCacheScope,
  getSessionCacheEntry,
  setSessionCacheEntry,
  type SessionCacheScope,
} from "../../../auth/model/session-cache";
import type { LibraryDecksState } from "./useLibraryDecks";

interface LibraryDecksCache {
  currentUserUuid: string | null;
  state: LibraryDecksState;
  onlyFavourites: boolean;
}

const LIBRARY_DECKS_CACHE_KEY = createSessionCacheKey<LibraryDecksCache>("library.decks");
type SaveChangeSource = "local" | "remote";
const saveChangeListeners = new Set<(source: SaveChangeSource) => void>();
const channel =
  typeof window !== "undefined" && typeof BroadcastChannel !== "undefined"
    ? new BroadcastChannel("etch-deck-save-changes")
    : null;

channel?.addEventListener("message", (event: MessageEvent<unknown>) => {
  if (event.data !== "saved-state-changed") {
    return;
  }

  // Read the current server state instead of replaying potentially delayed changes.
  deleteSessionCacheEntry(getCurrentSessionCacheScope(), LIBRARY_DECKS_CACHE_KEY);
  for (const listener of saveChangeListeners) {
    listener("remote");
  }
});

if (import.meta.hot) {
  import.meta.hot.dispose(() => channel?.close());
}

export function getCachedLibraryDecks(
  scope: SessionCacheScope | null = getCurrentSessionCacheScope(),
): LibraryDecksCache | null {
  return getSessionCacheEntry(scope, LIBRARY_DECKS_CACHE_KEY) ?? null;
}

export function setCachedLibraryDecks(
  cache: LibraryDecksCache | null,
  scope: SessionCacheScope | null = getCurrentSessionCacheScope(),
): void {
  if (cache === null) {
    deleteSessionCacheEntry(scope, LIBRARY_DECKS_CACHE_KEY);
  } else {
    setSessionCacheEntry(scope, LIBRARY_DECKS_CACHE_KEY, cache);
  }
}

export function updateLibraryDeckSavedState(deckUuid: string, isSaved: boolean): void {
  const scope = getCurrentSessionCacheScope();
  const cachedLibraryDecks = getCachedLibraryDecks(scope);
  if (isSaved) {
    // A newly saved deck may belong on a page that is already cached.
    setCachedLibraryDecks(null, scope);
  } else if (cachedLibraryDecks !== null) {
    const { state } = cachedLibraryDecks;
    const favouriteErrors = { ...state.favouriteErrors };
    const deleteErrors = { ...state.deleteErrors };
    delete favouriteErrors[deckUuid];
    delete deleteErrors[deckUuid];

    setCachedLibraryDecks(
      {
        ...cachedLibraryDecks,
        state: {
          ...state,
          decks: state.decks.filter((deck) => deck.uuid !== deckUuid),
          favouriteUpdatingDeckUuids: state.favouriteUpdatingDeckUuids.filter(
            (uuid) => uuid !== deckUuid,
          ),
          deletingDeckUuids: state.deletingDeckUuids.filter((uuid) => uuid !== deckUuid),
          favouriteErrors,
          deleteErrors,
        },
      },
      scope,
    );
  }

  for (const listener of saveChangeListeners) {
    listener("local");
  }
  channel?.postMessage("saved-state-changed");
}

export function subscribeToLibraryDeckSaveChanges(
  listener: (source: SaveChangeSource) => void,
): () => void {
  saveChangeListeners.add(listener);
  return () => {
    saveChangeListeners.delete(listener);
  };
}
