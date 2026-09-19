import { useCallback, useEffect, useRef, useState } from "react";
import {
  deleteDeckDetailsCard,
  deleteDeckFromDetails,
  getDeckDetailsCardBatch,
  getDeckDetailsInitialData,
  updateDeckDetailsCard,
} from "../api/deck-details-api";
import {
  getDeckDetailsBatchOffset,
  getDeckDetailsCardsForPage,
  getDeckDetailsPageCount,
} from "./deck-details-pagination";
import type {
  DeckDetails,
  DeckDetailsCard,
  UpdateDeckDetailsCardInput,
} from "./deck-details-types";

export type DeckDetailsStatus = "loading" | "success" | "error";

interface DeckDetailsState {
  status: DeckDetailsStatus;
  deck: DeckDetails | null;
  cardBatches: Readonly<Record<number, readonly DeckDetailsCard[]>>;
  currentPage: number;
  error: unknown | null;
  isPageLoading: boolean;
  pageError: unknown | null;
}

export interface UseDeckDetailsResult {
  status: DeckDetailsStatus;
  deck: DeckDetails | null;
  cards: readonly DeckDetailsCard[];
  currentPage: number;
  pageCount: number;
  error: unknown | null;
  isPageLoading: boolean;
  pageError: unknown | null;
  retry: () => void;
  retryPage: () => void;
  selectPage: (page: number) => void;
  updateCard: (cardUuid: string, input: UpdateDeckDetailsCardInput) => Promise<void>;
  deleteCard: (cardUuid: string) => Promise<void>;
  deleteDeck: () => Promise<void>;
}

const INITIAL_STATE: DeckDetailsState = {
  status: "loading",
  deck: null,
  cardBatches: {},
  currentPage: 1,
  error: null,
  isPageLoading: false,
  pageError: null,
};

export function useDeckDetails(deckUuid: string): UseDeckDetailsResult {
  const [state, setState] = useState<DeckDetailsState>(INITIAL_STATE);
  const initialControllerRef = useRef<AbortController | null>(null);
  const pageControllerRef = useRef<AbortController | null>(null);
  const deckDeleteControllerRef = useRef<AbortController | null>(null);
  const cardUpdateControllersRef = useRef(new Map<string, AbortController>());
  const cardDeleteControllersRef = useRef(new Map<string, AbortController>());
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

    void getDeckDetailsInitialData(deckUuid, controller.signal)
      .then(({ deck, cardBatch }) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState({
            status: "success",
            deck,
            cardBatches: { 0: cardBatch.cards },
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

      const pageCount = getDeckDetailsPageCount(state.deck.totalWordsCount);
      const targetPage = Math.min(Math.max(1, Math.floor(page)), Math.max(pageCount, 1));
      const batchOffset = getDeckDetailsBatchOffset(targetPage);
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

      void getDeckDetailsCardBatch(deckUuid, batchOffset, controller.signal)
        .then((cardBatch) => {
          if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
            setState((currentState) => ({
              ...currentState,
              cardBatches: {
                ...currentState.cardBatches,
                [batchOffset]: cardBatch.cards,
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

  const updateCard = useCallback(
    async (cardUuid: string, input: UpdateDeckDetailsCardInput): Promise<void> => {
      cardUpdateControllersRef.current.get(cardUuid)?.abort();
      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      cardUpdateControllersRef.current.set(cardUuid, controller);

      try {
        const updatedCard = await updateDeckDetailsCard(cardUuid, input, controller.signal);
        if (controller.signal.aborted || requestRevisionRef.current !== requestRevision) {
          return;
        }

        setState((currentState) => ({
          ...currentState,
          cardBatches: Object.fromEntries(
            Object.entries(currentState.cardBatches).map(([offset, cards]) => [
              offset,
              cards.map((card) => (card.uuid === cardUuid ? updatedCard : card)),
            ]),
          ),
        }));
      } finally {
        if (cardUpdateControllersRef.current.get(cardUuid) === controller) {
          cardUpdateControllersRef.current.delete(cardUuid);
        }
      }
    },
    [],
  );

  const deleteCard = useCallback(
    async (cardUuid: string): Promise<void> => {
      if (state.deck === null) {
        return;
      }

      cardDeleteControllersRef.current.get(cardUuid)?.abort();
      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      cardDeleteControllersRef.current.set(cardUuid, controller);

      try {
        await deleteDeckDetailsCard(cardUuid, controller.signal);
        if (controller.signal.aborted || requestRevisionRef.current !== requestRevision) {
          return;
        }

        const nextTotalWordsCount = Math.max(0, state.deck.totalWordsCount - 1);
        const nextPageCount = getDeckDetailsPageCount(nextTotalWordsCount);
        const nextPage = Math.min(state.currentPage, Math.max(nextPageCount, 1));
        const batchOffset = getDeckDetailsBatchOffset(nextPage);

        pageControllerRef.current?.abort();
        const refreshController = new AbortController();
        pageControllerRef.current = refreshController;
        setState((currentState) => ({
          ...currentState,
          deck:
            currentState.deck === null
              ? null
              : { ...currentState.deck, totalWordsCount: nextTotalWordsCount },
          cardBatches: {},
          currentPage: nextPage,
          isPageLoading: nextTotalWordsCount > 0,
          pageError: null,
        }));

        if (nextTotalWordsCount === 0) {
          pageControllerRef.current = null;
          return;
        }

        try {
          const cardBatch = await getDeckDetailsCardBatch(
            deckUuid,
            batchOffset,
            refreshController.signal,
          );
          if (!refreshController.signal.aborted && requestRevisionRef.current === requestRevision) {
            setState((currentState) => ({
              ...currentState,
              cardBatches: { [batchOffset]: cardBatch.cards },
              isPageLoading: false,
              pageError: null,
            }));
          }
        } catch (error: unknown) {
          if (!refreshController.signal.aborted && requestRevisionRef.current === requestRevision) {
            setState((currentState) => ({
              ...currentState,
              isPageLoading: false,
              pageError: error,
            }));
          }
        } finally {
          if (pageControllerRef.current === refreshController) {
            pageControllerRef.current = null;
          }
        }
      } finally {
        if (cardDeleteControllersRef.current.get(cardUuid) === controller) {
          cardDeleteControllersRef.current.delete(cardUuid);
        }
      }
    },
    [deckUuid, state.currentPage, state.deck],
  );

  const deleteDeck = useCallback(async (): Promise<void> => {
    deckDeleteControllerRef.current?.abort();
    const controller = new AbortController();
    deckDeleteControllerRef.current = controller;

    try {
      await deleteDeckFromDetails(deckUuid, controller.signal);
    } finally {
      if (deckDeleteControllerRef.current === controller) {
        deckDeleteControllerRef.current = null;
      }
    }
  }, [deckUuid]);

  useEffect(() => {
    const cardUpdateControllers = cardUpdateControllersRef.current;
    const cardDeleteControllers = cardDeleteControllersRef.current;
    loadFirstBatch();

    return () => {
      requestRevisionRef.current += 1;
      initialControllerRef.current?.abort();
      pageControllerRef.current?.abort();
      deckDeleteControllerRef.current?.abort();
      cardUpdateControllers.forEach((controller) => controller.abort());
      cardUpdateControllers.clear();
      cardDeleteControllers.forEach((controller) => controller.abort());
      cardDeleteControllers.clear();
    };
  }, [loadFirstBatch]);

  const pageCount = state.deck === null ? 0 : getDeckDetailsPageCount(state.deck.totalWordsCount);
  const batchOffset = getDeckDetailsBatchOffset(state.currentPage);
  const cards = getDeckDetailsCardsForPage(
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
    updateCard,
    deleteCard,
    deleteDeck,
  };
}
