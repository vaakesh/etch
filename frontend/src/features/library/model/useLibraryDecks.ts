import { useCallback, useEffect, useRef, useState } from "react";
import { getLibraryDeckPage } from "../api/library-api";
import type { LibraryDeck } from "./library-types";

export type LibraryDecksStatus = "loading" | "success" | "error";

interface LibraryDecksState {
  status: LibraryDecksStatus;
  decks: readonly LibraryDeck[];
  nextCursor: string | null;
  hasMore: boolean;
  error: unknown | null;
  isLoadingMore: boolean;
  loadMoreError: unknown | null;
}

interface UseLibraryDecksResult extends LibraryDecksState {
  retry: () => void;
  loadMore: () => void;
}

const INITIAL_STATE: LibraryDecksState = {
  status: "loading",
  decks: [],
  nextCursor: null,
  hasMore: false,
  error: null,
  isLoadingMore: false,
  loadMoreError: null,
};

function appendUniqueDecks(
  currentDecks: readonly LibraryDeck[],
  nextDecks: readonly LibraryDeck[],
): readonly LibraryDeck[] {
  const knownUuids = new Set(currentDecks.map((deck) => deck.uuid));
  return [...currentDecks, ...nextDecks.filter((deck) => !knownUuids.has(deck.uuid))];
}

export function useLibraryDecks(): UseLibraryDecksResult {
  const [state, setState] = useState<LibraryDecksState>(INITIAL_STATE);
  const initialControllerRef = useRef<AbortController | null>(null);
  const loadMoreControllerRef = useRef<AbortController | null>(null);
  const requestRevisionRef = useRef(0);

  const loadFirstPage = useCallback((): void => {
    initialControllerRef.current?.abort();
    loadMoreControllerRef.current?.abort();

    const controller = new AbortController();
    const requestRevision = requestRevisionRef.current + 1;
    requestRevisionRef.current = requestRevision;
    initialControllerRef.current = controller;
    loadMoreControllerRef.current = null;

    queueMicrotask(() => {
      if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
        setState(INITIAL_STATE);
      }
    });

    void getLibraryDeckPage(null, controller.signal)
      .then((page) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState({
            status: "success",
            decks: page.decks,
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
          setState({
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
  }, []);

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

    void getLibraryDeckPage(cursor, controller.signal)
      .then((page) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState((currentState) => ({
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
          setState((currentState) => ({
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
  }, [state.hasMore, state.isLoadingMore, state.nextCursor, state.status]);

  useEffect(() => {
    loadFirstPage();

    return () => {
      requestRevisionRef.current += 1;
      initialControllerRef.current?.abort();
      loadMoreControllerRef.current?.abort();
      initialControllerRef.current = null;
      loadMoreControllerRef.current = null;
    };
  }, [loadFirstPage]);

  return { ...state, retry: loadFirstPage, loadMore };
}
