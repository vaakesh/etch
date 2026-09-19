import { useCallback, useEffect, useRef, useState } from "react";
import { subscribeToLibraryDeckSaveChanges } from "../../library/model/library-decks-cache";
import { getCatalogDeckPage, setCatalogDeckSaved } from "../api/catalog-api";
import type { CatalogDeck } from "./catalog-types";

export type CatalogDecksStatus = "loading" | "success" | "error";

interface CatalogDecksState {
  status: CatalogDecksStatus;
  decks: readonly CatalogDeck[];
  page: number;
  hasMore: boolean;
  error: unknown | null;
  savingDeckUuids: readonly string[];
  saveErrors: Readonly<Record<string, CatalogDeckSaveFailure>>;
}

export interface CatalogDeckSaveFailure {
  error: unknown;
  intendedSavedState: boolean;
}

export interface UseCatalogDecksResult extends CatalogDecksState {
  retry: () => void;
  setSaved: (deckUuid: string, value: boolean) => void;
}

const INITIAL_STATE: CatalogDecksState = {
  status: "loading",
  decks: [],
  page: 0,
  hasMore: false,
  error: null,
  savingDeckUuids: [],
  saveErrors: {},
};

export function useCatalogDecks(searchQuery: string, page: number): UseCatalogDecksResult {
  const normalizedSearchQuery = searchQuery.trim();
  const [state, setState] = useState<CatalogDecksState>(INITIAL_STATE);
  const [retryRevision, setRetryRevision] = useState(0);
  const saveControllerRefs = useRef(new Map<string, AbortController>());

  useEffect(() => {
    const controller = new AbortController();
    const delay = normalizedSearchQuery.length > 0 ? 350 : 0;
    const saveControllers = saveControllerRefs.current;

    saveControllers.forEach((saveController) => saveController.abort());
    saveControllers.clear();
    queueMicrotask(() => {
      if (!controller.signal.aborted) {
        setState({ ...INITIAL_STATE, page });
      }
    });

    const timer = window.setTimeout(() => {
      void getCatalogDeckPage(
        page,
        normalizedSearchQuery.length === 0 ? null : normalizedSearchQuery,
        controller.signal,
      )
        .then((page) => {
          if (!controller.signal.aborted) {
            setState({
              status: "success",
              decks: page.decks,
              page: page.page,
              hasMore: page.hasMore,
              error: null,
              savingDeckUuids: [],
              saveErrors: {},
            });
          }
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted) {
            setState({ ...INITIAL_STATE, status: "error", error, page });
          }
        });
    }, delay);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
      saveControllers.forEach((saveController) => saveController.abort());
      saveControllers.clear();
    };
  }, [normalizedSearchQuery, page, retryRevision]);

  const retry = useCallback((): void => {
    setRetryRevision((revision) => revision + 1);
  }, []);

  useEffect(
    () =>
      subscribeToLibraryDeckSaveChanges((source) => {
        if (source === "remote") {
          retry();
        }
      }),
    [retry],
  );

  const setSaved = useCallback(
    (deckUuid: string, value: boolean): void => {
      const deck = state.decks.find((catalogDeck) => catalogDeck.uuid === deckUuid);
      if (
        state.status !== "success" ||
        deck === undefined ||
        deck.isSaved === value ||
        saveControllerRefs.current.has(deckUuid)
      ) {
        return;
      }

      const previousSavedState = deck.isSaved;
      const controller = new AbortController();
      saveControllerRefs.current.set(deckUuid, controller);

      setState((currentState) => {
        const saveErrors = { ...currentState.saveErrors };
        delete saveErrors[deckUuid];

        return {
          ...currentState,
          decks: currentState.decks.map((catalogDeck) =>
            catalogDeck.uuid === deckUuid ? { ...catalogDeck, isSaved: value } : catalogDeck,
          ),
          savingDeckUuids: [...currentState.savingDeckUuids, deckUuid],
          saveErrors,
        };
      });

      void setCatalogDeckSaved(deckUuid, value, controller.signal)
        .then(() => {
          if (!controller.signal.aborted) {
            setState((currentState) => ({
              ...currentState,
              savingDeckUuids: currentState.savingDeckUuids.filter((uuid) => uuid !== deckUuid),
            }));
          }
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted) {
            setState((currentState) => ({
              ...currentState,
              decks: currentState.decks.map((catalogDeck) =>
                catalogDeck.uuid === deckUuid
                  ? { ...catalogDeck, isSaved: previousSavedState }
                  : catalogDeck,
              ),
              savingDeckUuids: currentState.savingDeckUuids.filter((uuid) => uuid !== deckUuid),
              saveErrors: {
                ...currentState.saveErrors,
                [deckUuid]: { error, intendedSavedState: value },
              },
            }));
          }
        })
        .finally(() => {
          if (saveControllerRefs.current.get(deckUuid) === controller) {
            saveControllerRefs.current.delete(deckUuid);
          }
        });
    },
    [state.decks, state.status],
  );

  return { ...state, retry, setSaved };
}
