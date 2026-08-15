import { useCallback, useEffect, useRef, useState } from "react";
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

let cachedLibraryCards: LibraryCardsCache | null = null;

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
  const normalizedSearchQuery = searchQuery.trim().slice(0, LIBRARY_CARD_SEARCH_MAX_LENGTH);
  const cachedStateAtMount =
    cachedLibraryCards?.searchQuery === normalizedSearchQuery ? cachedLibraryCards.state : null;
  const hasLoadedOrStartedRef = useRef(cachedStateAtMount !== null);
  const [state, setState] = useState<LibraryCardsState>(cachedStateAtMount ?? INITIAL_STATE);
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

  const setCachedState = useCallback((update: LibraryCardsStateUpdate): void => {
    setState((currentState) => {
      const nextState = typeof update === "function" ? update(currentState) : update;
      cachedLibraryCards = {
        searchQuery: loadedSearchQueryRef.current,
        state: nextState,
      };
      return nextState;
    });
  }, []);

  const loadFirstPage = useCallback(
    (loadSearchQuery = searchQueryRef.current): void => {
      initialControllerRef.current?.abort();
      loadMoreControllerRef.current?.abort();
      createControllerRef.current?.abort();
      updateControllersRef.current.forEach((controller) => controller.abort());
      updateControllersRef.current.clear();
      deleteControllersRef.current.forEach((controller) => controller.abort());
      deleteControllersRef.current.clear();

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current + 1;
      const requestedSearchQuery = loadSearchQuery;
      requestRevisionRef.current = requestRevision;
      loadedSearchQueryRef.current = requestedSearchQuery;
      cachedLibraryCards = null;
      initialControllerRef.current = controller;
      loadMoreControllerRef.current = null;

      queueMicrotask(() => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
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
    [setCachedState],
  );

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
  }, [setCachedState, state.hasMore, state.isLoadingMore, state.nextCursor, state.status]);

  const retry = useCallback((): void => {
    loadFirstPage();
  }, [loadFirstPage]);

  const createCard = useCallback(
    async (input: CreateLibraryCardInput): Promise<void> => {
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
    [loadFirstPage],
  );

  const updateCard = useCallback(
    async (cardUuid: string, input: UpdateLibraryCardInput): Promise<void> => {
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
    [loadFirstPage, setCachedState],
  );

  const deleteCard = useCallback(
    async (cardUuid: string): Promise<void> => {
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
    [onDeleteSuccess, setCachedState],
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

    if (enabled && !hasLoadedOrStartedRef.current) {
      hasLoadedOrStartedRef.current = true;
      loadFirstPage();
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
  }, [enabled, loadFirstPage]);

  return {
    ...state,
    retry,
    loadMore,
    createCard,
    updateCard,
    deleteCard,
  };
}
