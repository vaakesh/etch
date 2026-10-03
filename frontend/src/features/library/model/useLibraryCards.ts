import { useCallback, useEffect, useRef, useState } from "react";
import { useSessionCacheScope } from "../../../auth/hooks/useSessionCacheScope";
import {
  createSessionCacheKey,
  deleteSessionCacheEntry,
  getSessionCacheEntry,
  isSessionCacheScopeActive,
  setSessionCacheEntry,
} from "../../../auth/model/session-cache";
import {
  createLibraryCard,
  deleteLibraryCard,
  getLibraryCardPage,
  updateLibraryCard,
} from "../api/library-api";
import type { CreateLibraryCardInput, LibraryCard, UpdateLibraryCardInput } from "./library-types";

export type LibraryCardsStatus = "loading" | "success" | "error";

interface LibraryCardsState {
  status: LibraryCardsStatus;
  cards: readonly LibraryCard[];
  nextCursor: string | null;
  hasMore: boolean;
  error: unknown | null;
  isLoadingMore: boolean;
  loadMoreError: unknown | null;
}

export interface UseLibraryCardsResult extends LibraryCardsState {
  retry: () => void;
  loadMore: () => void;
  createCard: (input: CreateLibraryCardInput) => Promise<void>;
  updateCard: (cardUuid: string, input: UpdateLibraryCardInput) => Promise<void>;
  deleteCard: (cardUuid: string) => Promise<void>;
}

export const LIBRARY_CARD_SEARCH_MAX_LENGTH = 50;

const INITIAL_STATE: LibraryCardsState = {
  status: "loading",
  cards: [],
  nextCursor: null,
  hasMore: false,
  error: null,
  isLoadingMore: false,
  loadMoreError: null,
};

type LibraryCardsStateUpdate =
  LibraryCardsState | ((currentState: LibraryCardsState) => LibraryCardsState);

interface LibraryCardsCache {
  searchQuery: string;
  state: LibraryCardsState;
}

const LIBRARY_CARDS_CACHE_KEY = createSessionCacheKey<LibraryCardsCache>("library.cards");

function appendUniqueCards(
  currentCards: readonly LibraryCard[],
  nextCards: readonly LibraryCard[],
): readonly LibraryCard[] {
  const knownCardUuids = new Set(currentCards.map((card) => card.uuid));

  return [...currentCards, ...nextCards.filter((card) => !knownCardUuids.has(card.uuid))];
}

export function useLibraryCards({
  enabled = true,
  onDeleteSuccess,
  searchQuery = "",
}: {
  enabled?: boolean;
  onDeleteSuccess?: () => void;
  searchQuery?: string;
} = {}): UseLibraryCardsResult {
  const cacheScope = useSessionCacheScope();
  const normalizedSearchQuery = searchQuery.trim().slice(0, LIBRARY_CARD_SEARCH_MAX_LENGTH);
  const cachedLibraryCards = getSessionCacheEntry(cacheScope, LIBRARY_CARDS_CACHE_KEY);
  const cachedStateAtMount =
    cachedLibraryCards?.searchQuery === normalizedSearchQuery ? cachedLibraryCards.state : null;
  const [state, setState] = useState<LibraryCardsState>(cachedStateAtMount ?? INITIAL_STATE);
  const [stateScopeKey, setStateScopeKey] = useState<string | null>(
    cachedStateAtMount === null ? null : (cacheScope?.key ?? null),
  );
  const loadedScopeKeyRef = useRef(cachedStateAtMount === null ? null : (cacheScope?.key ?? null));
  const initialControllerRef = useRef<AbortController | null>(null);
  const loadMoreControllerRef = useRef<AbortController | null>(null);
  const createControllerRef = useRef<AbortController | null>(null);
  const updateControllersRef = useRef(new Map<string, AbortController>());
  const deleteControllersRef = useRef(new Map<string, AbortController>());
  const cleanupTimerRef = useRef<number | null>(null);
  const requestRevisionRef = useRef(0);
  const searchQueryRef = useRef(normalizedSearchQuery);
  const loadedSearchQueryRef = useRef(normalizedSearchQuery);
  const previousSearchQueryRef = useRef(normalizedSearchQuery);

  const setCachedState = useCallback(
    (update: LibraryCardsStateUpdate): void => {
      if (!isSessionCacheScopeActive(cacheScope)) {
        return;
      }

      setStateScopeKey(cacheScope.key);
      setState((currentState) => {
        const nextState = typeof update === "function" ? update(currentState) : update;
        if (
          !setSessionCacheEntry(cacheScope, LIBRARY_CARDS_CACHE_KEY, {
            searchQuery: loadedSearchQueryRef.current,
            state: nextState,
          })
        ) {
          return currentState;
        }
        return nextState;
      });
    },
    [cacheScope],
  );

  const loadFirstPage = useCallback(
    (loadSearchQuery = searchQueryRef.current): void => {
      initialControllerRef.current?.abort();
      loadMoreControllerRef.current?.abort();
      createControllerRef.current?.abort();
      updateControllersRef.current.forEach((controller) => controller.abort());
      updateControllersRef.current.clear();
      deleteControllersRef.current.forEach((controller) => controller.abort());
      deleteControllersRef.current.clear();

      if (!isSessionCacheScopeActive(cacheScope)) {
        requestRevisionRef.current += 1;
        loadedScopeKeyRef.current = null;
        queueMicrotask(() => {
          setStateScopeKey(null);
          setState(INITIAL_STATE);
        });
        return;
      }

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current + 1;
      const requestedSearchQuery = loadSearchQuery;
      requestRevisionRef.current = requestRevision;
      loadedSearchQueryRef.current = requestedSearchQuery;
      loadedScopeKeyRef.current = cacheScope.key;
      deleteSessionCacheEntry(cacheScope, LIBRARY_CARDS_CACHE_KEY);
      initialControllerRef.current = controller;
      loadMoreControllerRef.current = null;

      queueMicrotask(() => {
        if (
          !controller.signal.aborted &&
          requestRevisionRef.current === requestRevision &&
          isSessionCacheScopeActive(cacheScope)
        ) {
          setStateScopeKey(cacheScope.key);
          setState(INITIAL_STATE);
        }
      });

      void getLibraryCardPage(
        null,
        controller.signal,
        requestedSearchQuery.length === 0 ? null : requestedSearchQuery,
      )
        .then((page) => {
          if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
            setCachedState({
              status: "success",
              cards: page.cards,
              nextCursor: page.nextCursor,
              hasMore: page.hasMore,
              error: null,
              isLoadingMore: false,
              loadMoreError: null,
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
    },
    [cacheScope, setCachedState],
  );

  const loadMore = useCallback((): void => {
    if (
      !isSessionCacheScopeActive(cacheScope) ||
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

    void getLibraryCardPage(
      cursor,
      controller.signal,
      loadedSearchQueryRef.current.length === 0 ? null : loadedSearchQueryRef.current,
    )
      .then((page) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setCachedState((currentState) => ({
            ...currentState,
            cards: appendUniqueCards(currentState.cards, page.cards),
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
  }, [
    cacheScope,
    setCachedState,
    state.hasMore,
    state.isLoadingMore,
    state.nextCursor,
    state.status,
  ]);

  const retry = useCallback((): void => {
    loadFirstPage();
  }, [loadFirstPage]);

  const createCard = useCallback(
    async (input: CreateLibraryCardInput): Promise<void> => {
      if (!isSessionCacheScopeActive(cacheScope)) {
        return;
      }
      createControllerRef.current?.abort();

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      createControllerRef.current = controller;

      try {
        await createLibraryCard(input, controller.signal);

        if (controller.signal.aborted || requestRevisionRef.current !== requestRevision) {
          return;
        }

        createControllerRef.current = null;
        loadFirstPage();
      } finally {
        if (createControllerRef.current === controller) {
          createControllerRef.current = null;
        }
      }
    },
    [cacheScope, loadFirstPage],
  );

  const updateCard = useCallback(
    async (cardUuid: string, input: UpdateLibraryCardInput): Promise<void> => {
      if (!isSessionCacheScopeActive(cacheScope)) {
        return;
      }
      updateControllersRef.current.get(cardUuid)?.abort();

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      updateControllersRef.current.set(cardUuid, controller);

      try {
        const updatedCard = await updateLibraryCard(cardUuid, input, controller.signal);

        if (controller.signal.aborted || requestRevisionRef.current !== requestRevision) {
          return;
        }

        if (loadedSearchQueryRef.current.length > 0) {
          loadFirstPage();
        } else {
          setCachedState((currentState) => ({
            ...currentState,
            cards: currentState.cards.map((card) =>
              card.uuid === cardUuid ? { ...card, ...updatedCard } : card,
            ),
          }));
        }
      } finally {
        if (updateControllersRef.current.get(cardUuid) === controller) {
          updateControllersRef.current.delete(cardUuid);
        }
      }
    },
    [cacheScope, loadFirstPage, setCachedState],
  );

  const deleteCard = useCallback(
    async (cardUuid: string): Promise<void> => {
      if (!isSessionCacheScopeActive(cacheScope)) {
        return;
      }
      deleteControllersRef.current.get(cardUuid)?.abort();

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      deleteControllersRef.current.set(cardUuid, controller);

      try {
        await deleteLibraryCard(cardUuid, controller.signal);

        if (controller.signal.aborted || requestRevisionRef.current !== requestRevision) {
          return;
        }

        setCachedState((currentState) => ({
          ...currentState,
          cards: currentState.cards.filter((card) => card.uuid !== cardUuid),
        }));

        onDeleteSuccess?.();
      } finally {
        if (deleteControllersRef.current.get(cardUuid) === controller) {
          deleteControllersRef.current.delete(cardUuid);
        }
      }
    },
    [cacheScope, onDeleteSuccess, setCachedState],
  );

  useEffect(() => {
    searchQueryRef.current = normalizedSearchQuery;

    if (!enabled) {
      return;
    }

    if (previousSearchQueryRef.current === normalizedSearchQuery) {
      return;
    }

    previousSearchQueryRef.current = normalizedSearchQuery;

    const timer = window.setTimeout(() => {
      loadFirstPage(normalizedSearchQuery);
    }, 450);

    return () => window.clearTimeout(timer);
  }, [enabled, loadFirstPage, normalizedSearchQuery]);

  useEffect(() => {
    const updateControllers = updateControllersRef.current;
    const deleteControllers = deleteControllersRef.current;
    if (cleanupTimerRef.current !== null) {
      window.clearTimeout(cleanupTimerRef.current);
      cleanupTimerRef.current = null;
    }

    if (cacheScope === null) {
      requestRevisionRef.current += 1;
      initialControllerRef.current?.abort();
      loadMoreControllerRef.current?.abort();
      createControllerRef.current?.abort();
      updateControllers.forEach((controller) => controller.abort());
      updateControllers.clear();
      deleteControllers.forEach((controller) => controller.abort());
      deleteControllers.clear();
      loadedScopeKeyRef.current = null;
      queueMicrotask(() => {
        setStateScopeKey(null);
        setState(INITIAL_STATE);
      });
    } else if (enabled && loadedScopeKeyRef.current !== cacheScope.key) {
      const cachedState = getSessionCacheEntry(cacheScope, LIBRARY_CARDS_CACHE_KEY);
      if (cachedState?.searchQuery === normalizedSearchQuery) {
        loadedScopeKeyRef.current = cacheScope.key;
        loadedSearchQueryRef.current = normalizedSearchQuery;
        queueMicrotask(() => {
          setStateScopeKey(cacheScope.key);
          setState(cachedState.state);
        });
      } else {
        queueMicrotask(loadFirstPage);
      }
    }

    return () => {
      cleanupTimerRef.current = window.setTimeout(() => {
        requestRevisionRef.current += 1;
        initialControllerRef.current?.abort();
        loadMoreControllerRef.current?.abort();
        createControllerRef.current?.abort();
        updateControllers.forEach((controller) => controller.abort());
        updateControllers.clear();
        deleteControllers.forEach((controller) => controller.abort());
        deleteControllers.clear();
        initialControllerRef.current = null;
        loadMoreControllerRef.current = null;
        cleanupTimerRef.current = null;
      }, 0);
    };
  }, [cacheScope, enabled, loadFirstPage, normalizedSearchQuery]);

  const visibleState =
    cacheScope !== null && stateScopeKey === cacheScope.key ? state : INITIAL_STATE;

  return {
    ...visibleState,
    retry,
    loadMore,
    createCard,
    updateCard,
    deleteCard,
  };
}
