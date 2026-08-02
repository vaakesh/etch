import { useCallback, useEffect, useRef, useState } from "react";
import {
  createLibraryDeck,
  deleteLibraryDeck,
  getFavouriteLibraryDeckPage,
  getLibraryDeckPage,
  setLibraryDeckFavourite,
} from "../api/library-api";
import type {
  CreateLibraryDeckInput,
  CreatedLibraryDeck,
  LibraryDeck,
  LibraryDeckItem,
} from "./library-types";

export type LibraryDecksStatus = "loading" | "success" | "error";

interface LibraryDecksState {
  status: LibraryDecksStatus;
  decks: readonly LibraryDeckItem[];
  nextCursor: string | null;
  hasMore: boolean;
  error: unknown | null;
  isLoadingMore: boolean;
  loadMoreError: unknown | null;
  favouriteUpdatingDeckUuids: readonly string[];
  favouriteErrors: Readonly<Record<string, unknown>>;
  deletingDeckUuids: readonly string[];
  deleteErrors: Readonly<Record<string, unknown>>;
}

export interface UseLibraryDecksResult extends LibraryDecksState {
  onlyFavourites: boolean;
  retry: () => void;
  loadMore: () => void;
  createDeck: (input: CreateLibraryDeckInput) => Promise<void>;
  deleteDeck: (deckUuid: string) => void;
  setOnlyFavourites: (value: boolean) => void;
  setFavourite: (deckUuid: string, value: boolean) => void;
}

const INITIAL_STATE: LibraryDecksState = {
  status: "loading",
  decks: [],
  nextCursor: null,
  hasMore: false,
  error: null,
  isLoadingMore: false,
  loadMoreError: null,
  favouriteUpdatingDeckUuids: [],
  favouriteErrors: {},
  deletingDeckUuids: [],
  deleteErrors: {},
};

interface LibraryDecksCache {
  currentUserUuid: string | null;
  state: LibraryDecksState;
  onlyFavourites: boolean;
}

type LibraryDecksStateUpdate =
  | LibraryDecksState
  | ((currentState: LibraryDecksState) => LibraryDecksState);

let cachedLibraryDecks: LibraryDecksCache | null = null;

function appendUniqueDecks(
  currentDecks: readonly LibraryDeckItem[],
  nextDecks: readonly LibraryDeckItem[],
): readonly LibraryDeckItem[] {
  const knownDeckUuids = new Set(currentDecks.map((deck) => deck.uuid));

  return [...currentDecks, ...nextDecks.filter((deck) => !knownDeckUuids.has(deck.uuid))];
}

function toLibraryDeck(deck: CreatedLibraryDeck, ownerUuid: string): LibraryDeck {
  return {
    uuid: deck.uuid,
    ownerUuid,
    title: deck.title,
    description: deck.description,
    totalWordsCount: deck.totalWordsCount,
    accuracy: 0,
    isFavourite: false,
    updatedAt: deck.updatedAt,
    cards: [],
  };
}

export function useLibraryDecks(currentUserUuid: string | null = null): UseLibraryDecksResult {
  const cachedStateAtMountRef = useRef(
    cachedLibraryDecks?.currentUserUuid === currentUserUuid ? cachedLibraryDecks : null,
  );
  const shouldLoadOnMountRef = useRef(cachedStateAtMountRef.current === null);
  const [state, setState] = useState<LibraryDecksState>(
    cachedStateAtMountRef.current?.state ?? INITIAL_STATE,
  );
  const [onlyFavourites, setOnlyFavouritesState] = useState(
    cachedStateAtMountRef.current?.onlyFavourites ?? false,
  );
  const onlyFavouritesRef = useRef(cachedStateAtMountRef.current?.onlyFavourites ?? false);
  const initialControllerRef = useRef<AbortController | null>(null);
  const loadMoreControllerRef = useRef<AbortController | null>(null);
  const createControllerRef = useRef<AbortController | null>(null);
  const favouriteControllerRefs = useRef(new Map<string, AbortController>());
  const deleteControllerRefs = useRef(new Map<string, AbortController>());
  const cleanupTimerRef = useRef<number | null>(null);
  const requestRevisionRef = useRef(0);

  const setCachedState = useCallback(
    (update: LibraryDecksStateUpdate): void => {
      setState((currentState) => {
        const nextState = typeof update === "function" ? update(currentState) : update;
        cachedLibraryDecks = {
          currentUserUuid,
          state: nextState,
          onlyFavourites: onlyFavouritesRef.current,
        };
        return nextState;
      });
    },
    [currentUserUuid],
  );

  const loadFirstPage = useCallback((loadOnlyFavourites = onlyFavouritesRef.current): void => {
    initialControllerRef.current?.abort();
    loadMoreControllerRef.current?.abort();
    createControllerRef.current?.abort();
    favouriteControllerRefs.current.forEach((controller) => controller.abort());
    favouriteControllerRefs.current.clear();
    deleteControllerRefs.current.forEach((controller) => controller.abort());
    deleteControllerRefs.current.clear();

    const controller = new AbortController();
    const requestRevision = requestRevisionRef.current + 1;
    requestRevisionRef.current = requestRevision;
    cachedLibraryDecks = null;
    initialControllerRef.current = controller;
    loadMoreControllerRef.current = null;

    queueMicrotask(() => {
      if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
        setState(INITIAL_STATE);
      }
    });

    const getDeckPage = loadOnlyFavourites ? getFavouriteLibraryDeckPage : getLibraryDeckPage;

    void getDeckPage(null, controller.signal)
      .then((page) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setCachedState({
            status: "success",
            decks: page.decks,
            nextCursor: page.nextCursor,
            hasMore: page.hasMore,
            error: null,
            isLoadingMore: false,
            loadMoreError: null,
            favouriteUpdatingDeckUuids: [],
            favouriteErrors: {},
            deletingDeckUuids: [],
            deleteErrors: {},
          });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setCachedState({
            ...INITIAL_STATE,
            status: "error",
            error,
          });
        }
      })
      .finally(() => {
        if (initialControllerRef.current === controller) {
          initialControllerRef.current = null;
        }
      });
  }, [setCachedState]);

  const loadMore = useCallback((): void => {
    if (
      state.status !== "success" ||
      state.isLoadingMore ||
      loadMoreControllerRef.current !== null ||
      !state.hasMore ||
      state.nextCursor === null
    ) {
      return;
    }

    const cursor = state.nextCursor;
    const requestRevision = requestRevisionRef.current;
    const controller = new AbortController();
    loadMoreControllerRef.current = controller;

    setState((currentState) => ({
      ...currentState,
      isLoadingMore: true,
      loadMoreError: null,
    }));

    const getDeckPage = onlyFavouritesRef.current
      ? getFavouriteLibraryDeckPage
      : getLibraryDeckPage;

    void getDeckPage(cursor, controller.signal)
      .then((page) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setCachedState((currentState) => ({
            ...currentState,
            decks: appendUniqueDecks(currentState.decks, page.decks),
            nextCursor: page.nextCursor,
            hasMore: page.hasMore,
            isLoadingMore: false,
            loadMoreError: null,
          }));
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setCachedState((currentState) => ({
            ...currentState,
            isLoadingMore: false,
            loadMoreError: error,
          }));
        }
      })
      .finally(() => {
        if (loadMoreControllerRef.current === controller) {
          loadMoreControllerRef.current = null;
        }
      });
  }, [setCachedState, state.hasMore, state.isLoadingMore, state.nextCursor, state.status]);

  const setFavourite = useCallback(
    (deckUuid: string, value: boolean): void => {
      if (
        state.status !== "success" ||
        !state.decks.some((deck) => deck.uuid === deckUuid) ||
        favouriteControllerRefs.current.has(deckUuid)
      ) {
        return;
      }

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      favouriteControllerRefs.current.set(deckUuid, controller);

      setState((currentState) => {
        const favouriteErrors = { ...currentState.favouriteErrors };
        delete favouriteErrors[deckUuid];

        return {
          ...currentState,
          favouriteUpdatingDeckUuids: [...currentState.favouriteUpdatingDeckUuids, deckUuid],
          favouriteErrors,
        };
      });

      void setLibraryDeckFavourite(deckUuid, value, controller.signal)
        .then((result) => {
          if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
            setCachedState((currentState) => ({
              ...currentState,
              decks:
                onlyFavouritesRef.current && !result.isFavourite
                  ? currentState.decks.filter((deck) => deck.uuid !== deckUuid)
                  : currentState.decks.map((deck) =>
                      deck.uuid === deckUuid ? { ...deck, isFavourite: result.isFavourite } : deck,
                    ),
              favouriteUpdatingDeckUuids: currentState.favouriteUpdatingDeckUuids.filter(
                (uuid) => uuid !== deckUuid,
              ),
            }));
          }
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
            setCachedState((currentState) => ({
              ...currentState,
              favouriteUpdatingDeckUuids: currentState.favouriteUpdatingDeckUuids.filter(
                (uuid) => uuid !== deckUuid,
              ),
              favouriteErrors: {
                ...currentState.favouriteErrors,
                [deckUuid]: error,
              },
            }));
          }
        })
        .finally(() => {
          if (favouriteControllerRefs.current.get(deckUuid) === controller) {
            favouriteControllerRefs.current.delete(deckUuid);
          }
        });
    },
    [setCachedState, state.decks, state.status],
  );

  const deleteDeck = useCallback(
    (deckUuid: string): void => {
      if (
        state.status !== "success" ||
        !state.decks.some((deck) => deck.uuid === deckUuid) ||
        deleteControllerRefs.current.has(deckUuid)
      ) {
        return;
      }

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      deleteControllerRefs.current.set(deckUuid, controller);

      setState((currentState) => {
        const deleteErrors = { ...currentState.deleteErrors };
        delete deleteErrors[deckUuid];

        return {
          ...currentState,
          deletingDeckUuids: [...currentState.deletingDeckUuids, deckUuid],
          deleteErrors,
        };
      });

      void deleteLibraryDeck(deckUuid, controller.signal)
        .then(() => {
          if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
            setCachedState((currentState) => ({
              ...currentState,
              decks: currentState.decks.filter((deck) => deck.uuid !== deckUuid),
              deletingDeckUuids: currentState.deletingDeckUuids.filter((uuid) => uuid !== deckUuid),
            }));
          }
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
            setCachedState((currentState) => ({
              ...currentState,
              deletingDeckUuids: currentState.deletingDeckUuids.filter((uuid) => uuid !== deckUuid),
              deleteErrors: {
                ...currentState.deleteErrors,
                [deckUuid]: error,
              },
            }));
          }
        })
        .finally(() => {
          if (deleteControllerRefs.current.get(deckUuid) === controller) {
            deleteControllerRefs.current.delete(deckUuid);
          }
        });
    },
    [setCachedState, state.decks, state.status],
  );

  const setOnlyFavourites = useCallback(
    (value: boolean): void => {
      if (onlyFavouritesRef.current === value) {
        return;
      }

      onlyFavouritesRef.current = value;
      setOnlyFavouritesState(value);
      loadFirstPage(value);
    },
    [loadFirstPage],
  );

  const retry = useCallback((): void => {
    loadFirstPage(onlyFavouritesRef.current);
  }, [loadFirstPage]);

  const createDeck = useCallback(
    async (input: CreateLibraryDeckInput): Promise<void> => {
      createControllerRef.current?.abort();

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      createControllerRef.current = controller;

      try {
        const createdDeck = await createLibraryDeck(input, controller.signal);

        if (controller.signal.aborted || requestRevisionRef.current !== requestRevision) {
          return;
        }

        const shouldReloadAllDecks = onlyFavouritesRef.current;
        initialControllerRef.current?.abort();
        loadMoreControllerRef.current?.abort();
        favouriteControllerRefs.current.forEach((favouriteController) =>
          favouriteController.abort(),
        );
        favouriteControllerRefs.current.clear();
        deleteControllerRefs.current.forEach((deleteController) => deleteController.abort());
        deleteControllerRefs.current.clear();
        initialControllerRef.current = null;
        loadMoreControllerRef.current = null;
        requestRevisionRef.current += 1;
        onlyFavouritesRef.current = false;
        setOnlyFavouritesState(false);

        if (currentUserUuid !== null) {
          const libraryDeck = toLibraryDeck(createdDeck, currentUserUuid);
          setCachedState((currentState) => ({
            ...(currentState.status === "success" ? currentState : INITIAL_STATE),
            status: "success",
            decks: [
              libraryDeck,
              ...currentState.decks.filter((deck) => deck.uuid !== libraryDeck.uuid),
            ],
            error: null,
            isLoadingMore: false,
            loadMoreError: null,
            favouriteUpdatingDeckUuids: [],
            favouriteErrors: {},
            deletingDeckUuids: [],
            deleteErrors: {},
          }));
        }

        createControllerRef.current = null;
        if (shouldReloadAllDecks || currentUserUuid === null) {
          loadFirstPage(false);
        }
      } finally {
        if (createControllerRef.current === controller) {
          createControllerRef.current = null;
        }
      }
    },
    [currentUserUuid, loadFirstPage, setCachedState],
  );

  useEffect(() => {
    const favouriteControllers = favouriteControllerRefs.current;
    const deleteControllers = deleteControllerRefs.current;
    if (cleanupTimerRef.current !== null) {
      window.clearTimeout(cleanupTimerRef.current);
      cleanupTimerRef.current = null;
    }

    if (shouldLoadOnMountRef.current) {
      shouldLoadOnMountRef.current = false;
      loadFirstPage();
    }

    return () => {
      cleanupTimerRef.current = window.setTimeout(() => {
        requestRevisionRef.current += 1;
        initialControllerRef.current?.abort();
        loadMoreControllerRef.current?.abort();
        createControllerRef.current?.abort();
        favouriteControllers.forEach((controller) => controller.abort());
        favouriteControllers.clear();
        deleteControllers.forEach((controller) => controller.abort());
        deleteControllers.clear();
        initialControllerRef.current = null;
        loadMoreControllerRef.current = null;
        cleanupTimerRef.current = null;
      }, 0);
    };
  }, [loadFirstPage]);

  return {
    ...state,
    onlyFavourites,
    retry,
    loadMore,
    createDeck,
    deleteDeck,
    setOnlyFavourites,
    setFavourite,
  };
}
