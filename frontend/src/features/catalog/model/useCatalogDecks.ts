import { useCallback, useEffect, useRef, useState } from "react";
import { useSessionCacheScope } from "../../../auth/hooks/useSessionCacheScope";
import { subscribeToLibraryDeckSaveChanges } from "../../library/model/library-decks-cache";
import { getCatalogDeckPage, setCatalogDeckSaved } from "../api/catalog-api";
import {
  clearCachedCatalogDeckPage,
  getCachedCatalogDeckPage,
  setCachedCatalogDeckPage,
} from "./catalog-decks-cache";
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
  const cacheScope = useSessionCacheScope();
  const normalizedSearchQuery = searchQuery.trim();
  const cachedPageAtMount = getCachedCatalogDeckPage(cacheScope, normalizedSearchQuery, page);
  const [state, setState] = useState<CatalogDecksState>(
    cachedPageAtMount === null
      ? INITIAL_STATE
      : {
          ...INITIAL_STATE,
          status: "success",
          decks: cachedPageAtMount.decks,
          page: cachedPageAtMount.page,
          hasMore: cachedPageAtMount.hasMore,
        },
  );
  const [retryRevision, setRetryRevision] = useState(0);
  const restoredPageRef = useRef(
    cachedPageAtMount === null
      ? null
      : { scopeKey: cacheScope?.key, searchQuery: normalizedSearchQuery, page },
  );
  const saveControllerRefs = useRef(new Map<string, AbortController>());

  useEffect(() => {
    const saveControllers = saveControllerRefs.current;
    const restoredPage = restoredPageRef.current;
    if (
      retryRevision === 0 &&
      restoredPage?.scopeKey === cacheScope?.key &&
      restoredPage?.searchQuery === normalizedSearchQuery &&
      restoredPage?.page === page
    ) {
      return () => {
        saveControllers.forEach((saveController) => saveController.abort());
        saveControllers.clear();
      };
    }
    restoredPageRef.current = null;

    const controller = new AbortController();
    const delay = normalizedSearchQuery.length > 0 ? 350 : 0;
    clearCachedCatalogDeckPage(cacheScope);
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
            setCachedCatalogDeckPage(cacheScope, normalizedSearchQuery, page);
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
  }, [cacheScope, normalizedSearchQuery, page, retryRevision]);

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
      clearCachedCatalogDeckPage(cacheScope);

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
    [cacheScope, state.decks, state.status],
  );

  return { ...state, retry, setSaved };
}
