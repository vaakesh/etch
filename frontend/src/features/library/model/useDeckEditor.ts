import { useCallback, useEffect, useRef, useState } from "react";
import {
  getEditableLibraryDeck,
  getLibraryDeckCardPage,
  removeLibraryCardFromDeck,
  updateEditableLibraryDeck,
  updateLibraryCard,
} from "../api/library-api";
import type {
  EditableLibraryCard,
  EditableLibraryDeck,
  UpdateLibraryCardInput,
  UpdateLibraryDeckInput,
} from "./library-types";

export type DeckEditorStatus = "loading" | "success" | "error";

interface DeckEditorState {
  status: DeckEditorStatus;
  deck: EditableLibraryDeck | null;
  cards: readonly EditableLibraryCard[];
  nextOffset: number;
  hasMore: boolean;
  error: unknown | null;
  isLoadingMore: boolean;
  loadMoreError: unknown | null;
}

export interface UseDeckEditorResult extends DeckEditorState {
  retry: () => void;
  loadMore: () => void;
  saveDeck: (input: UpdateLibraryDeckInput) => Promise<void>;
  updateCard: (cardUuid: string, input: UpdateLibraryCardInput) => Promise<void>;
  removeCard: (cardUuid: string) => Promise<void>;
}

const INITIAL_STATE: DeckEditorState = {
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
  currentCards: readonly EditableLibraryCard[],
  nextCards: readonly EditableLibraryCard[],
): readonly EditableLibraryCard[] {
  const knownCardUuids = new Set(currentCards.map((card) => card.uuid));

  return [...currentCards, ...nextCards.filter((card) => !knownCardUuids.has(card.uuid))];
}

export function useDeckEditor(deckUuid: string): UseDeckEditorResult {
  const [state, setState] = useState<DeckEditorState>(INITIAL_STATE);
  const initialControllerRef = useRef<AbortController | null>(null);
  const loadMoreControllerRef = useRef<AbortController | null>(null);
  const deckUpdateControllerRef = useRef<AbortController | null>(null);
  const cardUpdateControllersRef = useRef(new Map<string, AbortController>());
  const cardRemoveControllersRef = useRef(new Map<string, AbortController>());
  const requestRevisionRef = useRef(0);

  const loadFirstPage = useCallback((): void => {
    initialControllerRef.current?.abort();
    loadMoreControllerRef.current?.abort();
    deckUpdateControllerRef.current?.abort();
    cardUpdateControllersRef.current.forEach((controller) => controller.abort());
    cardUpdateControllersRef.current.clear();
    cardRemoveControllersRef.current.forEach((controller) => controller.abort());
    cardRemoveControllersRef.current.clear();

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
      getEditableLibraryDeck(deckUuid, controller.signal),
      getLibraryDeckCardPage(deckUuid, 0, controller.signal),
    ])
      .then(([deck, cardPage]) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState({
            status: "success",
            deck,
            cards: cardPage.cards,
            nextOffset: cardPage.nextOffset,
            hasMore: cardPage.hasMore,
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
      state.isLoadingMore ||
      loadMoreControllerRef.current !== null ||
      cardRemoveControllersRef.current.size > 0 ||
      !state.hasMore
    ) {
      return;
    }

    const offset = state.nextOffset;
    const requestRevision = requestRevisionRef.current;
    const controller = new AbortController();
    loadMoreControllerRef.current = controller;

    setState((currentState) => ({
      ...currentState,
      isLoadingMore: true,
      loadMoreError: null,
    }));

    void getLibraryDeckCardPage(deckUuid, offset, controller.signal)
      .then((page) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState((currentState) => ({
            ...currentState,
            cards: appendUniqueCards(currentState.cards, page.cards),
            nextOffset: page.nextOffset,
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
  }, [deckUuid, state.hasMore, state.isLoadingMore, state.nextOffset, state.status]);

  const saveDeck = useCallback(
    async (input: UpdateLibraryDeckInput): Promise<void> => {
      deckUpdateControllerRef.current?.abort();

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      deckUpdateControllerRef.current = controller;

      try {
        const updatedDeck = await updateEditableLibraryDeck(deckUuid, input, controller.signal);

        if (controller.signal.aborted || requestRevisionRef.current !== requestRevision) {
          return;
        }

        setState((currentState) => ({
          ...currentState,
          deck:
            currentState.deck === null
              ? updatedDeck
              : {
                  ...updatedDeck,
                  totalWordsCount: currentState.deck.totalWordsCount,
                },
        }));
      } finally {
        if (deckUpdateControllerRef.current === controller) {
          deckUpdateControllerRef.current = null;
        }
      }
    },
    [deckUuid],
  );

  const updateCard = useCallback(
    async (cardUuid: string, input: UpdateLibraryCardInput): Promise<void> => {
      cardUpdateControllersRef.current.get(cardUuid)?.abort();

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      cardUpdateControllersRef.current.set(cardUuid, controller);

      try {
        const updatedCard = await updateLibraryCard(cardUuid, input, controller.signal);

        if (controller.signal.aborted || requestRevisionRef.current !== requestRevision) {
          return;
        }

        setState((currentState) => ({
          ...currentState,
          cards: currentState.cards.map((card) =>
            card.uuid === cardUuid ? { ...card, ...updatedCard } : card,
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

  const removeCard = useCallback(
    async (cardUuid: string): Promise<void> => {
      cardRemoveControllersRef.current.get(cardUuid)?.abort();
      loadMoreControllerRef.current?.abort();
      loadMoreControllerRef.current = null;

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      cardRemoveControllersRef.current.set(cardUuid, controller);
      setState((currentState) => ({
        ...currentState,
        isLoadingMore: false,
        loadMoreError: null,
      }));

      try {
        await removeLibraryCardFromDeck(deckUuid, cardUuid, controller.signal);

        if (controller.signal.aborted || requestRevisionRef.current !== requestRevision) {
          return;
        }

        setState((currentState) => {
          const didRemoveCard = currentState.cards.some((card) => card.uuid === cardUuid);

          return {
            ...currentState,
            deck:
              didRemoveCard && currentState.deck !== null
                ? {
                    ...currentState.deck,
                    totalWordsCount: Math.max(0, currentState.deck.totalWordsCount - 1),
                  }
                : currentState.deck,
            cards: currentState.cards.filter((card) => card.uuid !== cardUuid),
            nextOffset: didRemoveCard
              ? Math.max(0, currentState.nextOffset - 1)
              : currentState.nextOffset,
          };
        });
      } finally {
        if (cardRemoveControllersRef.current.get(cardUuid) === controller) {
          cardRemoveControllersRef.current.delete(cardUuid);
        }
      }
    },
    [deckUuid],
  );

  useEffect(() => {
    const cardUpdateControllers = cardUpdateControllersRef.current;
    const cardRemoveControllers = cardRemoveControllersRef.current;
    loadFirstPage();

    return () => {
      requestRevisionRef.current += 1;
      initialControllerRef.current?.abort();
      loadMoreControllerRef.current?.abort();
      deckUpdateControllerRef.current?.abort();
      cardUpdateControllers.forEach((controller) => controller.abort());
      cardUpdateControllers.clear();
      cardRemoveControllers.forEach((controller) => controller.abort());
      cardRemoveControllers.clear();
      initialControllerRef.current = null;
      loadMoreControllerRef.current = null;
      deckUpdateControllerRef.current = null;
    };
  }, [loadFirstPage]);

  return {
    ...state,
    retry: loadFirstPage,
    loadMore,
    saveDeck,
    updateCard,
    removeCard,
  };
}
