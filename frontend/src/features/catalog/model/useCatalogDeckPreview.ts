import { useCallback, useEffect, useRef, useState } from "react";
import { getCatalogDeckPreviewInitialData, getCatalogPreviewCardPage } from "../api/catalog-api";
import {
  getCatalogPreviewBatchOffset,
  getCatalogPreviewCardsForPage,
  getCatalogPreviewPageCount,
} from "./catalog-preview-pagination";
import type { CatalogDeckPreview, CatalogPreviewCard } from "./catalog-types";

export type CatalogDeckPreviewStatus = "loading" | "success" | "error";

interface CatalogDeckPreviewState {
  status: CatalogDeckPreviewStatus;
  deck: CatalogDeckPreview | null;
  cardBatches: Readonly<Record<number, readonly CatalogPreviewCard[]>>;
  currentPage: number;
  error: unknown | null;
  isPageLoading: boolean;
  pageError: unknown | null;
}

export interface UseCatalogDeckPreviewResult {
  status: CatalogDeckPreviewStatus;
  deck: CatalogDeckPreview | null;
  cards: readonly CatalogPreviewCard[];
  currentPage: number;
  pageCount: number;
  error: unknown | null;
  isPageLoading: boolean;
  pageError: unknown | null;
  retry: () => void;
  retryPage: () => void;
  selectPage: (page: number) => void;
}

const INITIAL_STATE: CatalogDeckPreviewState = {
  status: "loading",
  deck: null,
  cardBatches: {},
  currentPage: 1,
  error: null,
  isPageLoading: false,
  pageError: null,
};

export function useCatalogDeckPreview(deckUuid: string): UseCatalogDeckPreviewResult {
  const [state, setState] = useState<CatalogDeckPreviewState>(INITIAL_STATE);
  const initialControllerRef = useRef<AbortController | null>(null);
  const pageControllerRef = useRef<AbortController | null>(null);
  const requestRevisionRef = useRef(0);

  const loadFirstBatch = useCallback((): void => {
    initialControllerRef.current?.abort();
    pageControllerRef.current?.abort();

    const controller = new AbortController();
    const requestRevision = requestRevisionRef.current + 1;
    requestRevisionRef.current = requestRevision;
    initialControllerRef.current = controller;
    pageControllerRef.current = null;

    queueMicrotask(() => {
      if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
        setState(INITIAL_STATE);
      }
    });

    void getCatalogDeckPreviewInitialData(deckUuid, controller.signal)
      .then(({ deck, cardPage }) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState({
            status: "success",
            deck,
            cardBatches: { 0: cardPage.cards },
            currentPage: 1,
            error: null,
            isPageLoading: false,
            pageError: null,
          });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState({ ...INITIAL_STATE, status: "error", error });
        }
      })
      .finally(() => {
        if (initialControllerRef.current === controller) {
          initialControllerRef.current = null;
        }
      });
  }, [deckUuid]);

  const loadPage = useCallback(
    (page: number, force = false): void => {
      if (state.status !== "success" || state.deck === null) {
        return;
      }

      const pageCount = getCatalogPreviewPageCount(state.deck.totalWordsCount);
      const targetPage = Math.min(Math.max(1, Math.floor(page)), Math.max(pageCount, 1));
      const batchOffset = getCatalogPreviewBatchOffset(targetPage);
      const cachedCards = state.cardBatches[batchOffset];

      pageControllerRef.current?.abort();
      pageControllerRef.current = null;

      if (cachedCards !== undefined && !force) {
        setState((currentState) => ({
          ...currentState,
          currentPage: targetPage,
          isPageLoading: false,
          pageError: null,
        }));
        return;
      }

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      pageControllerRef.current = controller;
      setState((currentState) => ({
        ...currentState,
        currentPage: targetPage,
        isPageLoading: true,
        pageError: null,
      }));

      void getCatalogPreviewCardPage(deckUuid, batchOffset, controller.signal)
        .then((cardPage) => {
          if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
            setState((currentState) => ({
              ...currentState,
              cardBatches: {
                ...currentState.cardBatches,
                [batchOffset]: cardPage.cards,
              },
              isPageLoading: false,
              pageError: null,
            }));
          }
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
            setState((currentState) => ({
              ...currentState,
              isPageLoading: false,
              pageError: error,
            }));
          }
        })
        .finally(() => {
          if (pageControllerRef.current === controller) {
            pageControllerRef.current = null;
          }
        });
    },
    [deckUuid, state.cardBatches, state.deck, state.status],
  );

  useEffect(() => {
    loadFirstBatch();

    return () => {
      requestRevisionRef.current += 1;
      initialControllerRef.current?.abort();
      pageControllerRef.current?.abort();
      initialControllerRef.current = null;
      pageControllerRef.current = null;
    };
  }, [loadFirstBatch]);

  const pageCount =
    state.deck === null ? 0 : getCatalogPreviewPageCount(state.deck.totalWordsCount);
  const batchOffset = getCatalogPreviewBatchOffset(state.currentPage);
  const cards = getCatalogPreviewCardsForPage(
    state.cardBatches[batchOffset] ?? [],
    batchOffset,
    state.currentPage,
  );

  return {
    status: state.status,
    deck: state.deck,
    cards,
    currentPage: state.currentPage,
    pageCount,
    error: state.error,
    isPageLoading: state.isPageLoading,
    pageError: state.pageError,
    retry: loadFirstBatch,
    retryPage: () => loadPage(state.currentPage, true),
    selectPage: loadPage,
  };
}
