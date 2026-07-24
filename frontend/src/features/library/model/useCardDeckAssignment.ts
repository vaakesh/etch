import { useCallback, useEffect, useRef, useState } from "react";
import { addLibraryCardToDeck, getLibraryDeckOptions } from "../api/library-api";
import type { LibraryCardDeckAddStatus, LibraryDeckOption } from "./library-types";

export type CardDeckAssignmentStatus = "loading" | "success" | "error";

interface CardDeckAssignmentState {
  status: CardDeckAssignmentStatus;
  decks: readonly LibraryDeckOption[];
  error: unknown | null;
}

export type CardDeckAssignmentOutcome =
  | {
      deckUuid: string;
      status: LibraryCardDeckAddStatus;
    }
  | {
      deckUuid: string;
      status: "failed";
      error: unknown;
    };

export interface UseCardDeckAssignmentResult extends CardDeckAssignmentState {
  retry: () => void;
  assignToDecks: (deckUuids: readonly string[]) => Promise<readonly CardDeckAssignmentOutcome[]>;
}

const INITIAL_STATE: CardDeckAssignmentState = {
  status: "loading",
  decks: [],
  error: null,
};

export async function assignCardToDecks(
  cardUuid: string,
  deckUuids: readonly string[],
  signal?: AbortSignal,
): Promise<readonly CardDeckAssignmentOutcome[]> {
  const uniqueDeckUuids = [...new Set(deckUuids)];
  const settlements = await Promise.allSettled(
    uniqueDeckUuids.map((deckUuid) => addLibraryCardToDeck(deckUuid, cardUuid, signal)),
  );

  return settlements.map((settlement, index) => {
    const deckUuid = uniqueDeckUuids[index];

    if (settlement.status === "fulfilled") {
      return { deckUuid, status: settlement.value };
    }

    return { deckUuid, status: "failed", error: settlement.reason };
  });
}

export function useCardDeckAssignment(cardUuid: string): UseCardDeckAssignmentResult {
  const [state, setState] = useState<CardDeckAssignmentState>(INITIAL_STATE);
  const loadControllerRef = useRef<AbortController | null>(null);
  const saveControllerRef = useRef<AbortController | null>(null);
  const requestRevisionRef = useRef(0);

  const loadDecks = useCallback((): void => {
    loadControllerRef.current?.abort();

    const controller = new AbortController();
    const requestRevision = requestRevisionRef.current + 1;
    requestRevisionRef.current = requestRevision;
    loadControllerRef.current = controller;

    queueMicrotask(() => {
      if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
        setState(INITIAL_STATE);
      }
    });

    void getLibraryDeckOptions(controller.signal)
      .then((decks) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState({ status: "success", decks, error: null });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState({ status: "error", decks: [], error });
        }
      })
      .finally(() => {
        if (loadControllerRef.current === controller) {
          loadControllerRef.current = null;
        }
      });
  }, []);

  const assignToDecks = useCallback(
    async (deckUuids: readonly string[]): Promise<readonly CardDeckAssignmentOutcome[]> => {
      if (deckUuids.length === 0) {
        return [];
      }

      saveControllerRef.current?.abort();
      const controller = new AbortController();
      saveControllerRef.current = controller;

      try {
        return await assignCardToDecks(cardUuid, deckUuids, controller.signal);
      } finally {
        if (saveControllerRef.current === controller) {
          saveControllerRef.current = null;
        }
      }
    },
    [cardUuid],
  );

  useEffect(() => {
    loadDecks();

    return () => {
      requestRevisionRef.current += 1;
      loadControllerRef.current?.abort();
      saveControllerRef.current?.abort();
      loadControllerRef.current = null;
      saveControllerRef.current = null;
    };
  }, [loadDecks]);

  return {
    ...state,
    retry: loadDecks,
    assignToDecks,
  };
}
