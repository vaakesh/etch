import { useCallback, useEffect, useRef, useState } from "react";
import { getCatalogDeckPreview, getCatalogPreviewCardPage } from "../api/catalog-api";
import type { CatalogDeckPreview, CatalogPreviewCard } from "./catalog-types";

export type CatalogDeckPreviewStatus = "loading" | "success" | "error";

interface CatalogDeckPreviewState {
  status: CatalogDeckPreviewStatus;
  deck: CatalogDeckPreview | null;
  cards: readonly CatalogPreviewCard[];
  nextOffset: number;
  hasMore: boolean;
  error: unknown | null;
  isLoadingMore: boolean;
  loadMoreError: unknown | null;
}

export interface UseCatalogDeckPreviewResult extends CatalogDeckPreviewState {
  retry: () => void;
  loadMore: () => void;
}

const INITIAL_STATE: CatalogDeckPreviewState = {
  status: "loading",
  deck: null,
  cards: [],
  nextOffset: 0,
  hasMore: false,
  error: null,
  isLoadingMore: false,
  loadMoreError: null,
};

function appendUniqueCards(
  currentCards: readonly CatalogPreviewCard[],
  nextCards: readonly CatalogPreviewCard[],
): readonly CatalogPreviewCard[] {
  const knownCardUuids = new Set(currentCards.map((card) => card.uuid));

  return [...currentCards, ...nextCards.filter((card) => !knownCardUuids.has(card.uuid))];
}

function pageHasMore(
  loadedCount: number,
  returnedFullPage: boolean,
  totalWordsCount: number,
): boolean {
  return returnedFullPage && loadedCount < totalWordsCount;
}

export function useCatalogDeckPreview(deckUuid: string): UseCatalogDeckPreviewResult {
  const [state, setState] = useState<CatalogDeckPreviewState>(INITIAL_STATE);
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

    void Promise.all([
      getCatalogDeckPreview(deckUuid, controller.signal),
      getCatalogPreviewCardPage(deckUuid, 0, controller.signal),
    ])
      .then(([deck, cardPage]) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState({
            status: "success",
            deck,
            cards: cardPage.cards,
            nextOffset: cardPage.nextOffset,
            hasMore: pageHasMore(cardPage.nextOffset, cardPage.hasMore, deck.totalWordsCount),
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
  }, [deckUuid]);

  const loadMore = useCallback((): void => {
    if (
      state.status !== "success" ||
      state.deck === null ||
      !state.hasMore ||
      state.isLoadingMore ||
      loadMoreControllerRef.current !== null
    ) {
      return;
    }

    const offset = state.nextOffset;
    const totalWordsCount = state.deck.totalWordsCount;
    const requestRevision = requestRevisionRef.current;
    const controller = new AbortController();
    loadMoreControllerRef.current = controller;

    setState((currentState) => ({
      ...currentState,
      isLoadingMore: true,
      loadMoreError: null,
    }));

    void getCatalogPreviewCardPage(deckUuid, offset, controller.signal)
      .then((page) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState((currentState) => ({
            ...currentState,
            cards: appendUniqueCards(currentState.cards, page.cards),
            nextOffset: page.nextOffset,
            hasMore: pageHasMore(page.nextOffset, page.hasMore, totalWordsCount),
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
  }, [deckUuid, state.deck, state.hasMore, state.isLoadingMore, state.nextOffset, state.status]);

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
