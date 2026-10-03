import { useCallback, useEffect, useRef, useState } from "react";
import {
  ARCHIVE_CARD_BATCH_SIZE,
  getArchiveCards,
  getArchivedDeck,
  getArchiveOffers,
  preserveArchivedDeck,
} from "../api/archive-api";
import type { ArchiveCard, ArchivedDeck, ArchiveOffer, PreservedArchive } from "./archive-types";

type LoadStatus = "loading" | "success" | "error";

interface OffersState {
  status: LoadStatus;
  offers: readonly ArchiveOffer[];
  error: unknown | null;
}

interface PreviewState {
  status: LoadStatus;
  deck: ArchivedDeck | null;
  cards: readonly ArchiveCard[];
  error: unknown | null;
  isLoadingMore: boolean;
  loadMoreError: unknown | null;
}

const INITIAL_OFFERS: OffersState = { status: "loading", offers: [], error: null };
const INITIAL_PREVIEW: PreviewState = {
  status: "loading",
  deck: null,
  cards: [],
  error: null,
  isLoadingMore: false,
  loadMoreError: null,
};

export function usePreserveArchivedDeck() {
  const [pendingUuid, setPendingUuid] = useState<string | null>(null);
  const [failedUuid, setFailedUuid] = useState<string | null>(null);
  const [error, setError] = useState<unknown | null>(null);
  const [deletedCopyUuid, setDeletedCopyUuid] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const preserve = useCallback(async (deckUuid: string): Promise<PreservedArchive | null> => {
    if (controllerRef.current !== null) return null;
    const controller = new AbortController();
    controllerRef.current = controller;
    setPendingUuid(deckUuid);
    setFailedUuid(null);
    setError(null);
    try {
      const result = await preserveArchivedDeck(deckUuid, controller.signal);
      if (controller.signal.aborted) return null;
      if (result.copyDeleted) setDeletedCopyUuid(deckUuid);
      return result;
    } catch (caught: unknown) {
      if (!controller.signal.aborted) {
        setFailedUuid(deckUuid);
        setError(caught);
      }
      return null;
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        if (!controller.signal.aborted) setPendingUuid(null);
      }
    }
  }, []);

  return { preserve, pendingUuid, failedUuid, error, deletedCopyUuid };
}

export function useArchiveOffers() {
  const [state, setState] = useState<OffersState>(INITIAL_OFFERS);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    queueMicrotask(() => {
      if (!controller.signal.aborted) setState(INITIAL_OFFERS);
    });
    void getArchiveOffers(controller.signal)
      .then((offers) => {
        if (!controller.signal.aborted) setState({ status: "success", offers, error: null });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setState({ status: "error", offers: [], error });
      });
    return () => controller.abort();
  }, [revision]);

  const retry = useCallback(() => setRevision((value) => value + 1), []);
  return { ...state, retry };
}

export function useArchivePreview(deckUuid: string) {
  const [state, setState] = useState<PreviewState>(INITIAL_PREVIEW);
  const [revision, setRevision] = useState(0);
  const moreControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    moreControllerRef.current?.abort();
    queueMicrotask(() => {
      if (!controller.signal.aborted) setState(INITIAL_PREVIEW);
    });
    void Promise.all([
      getArchivedDeck(deckUuid, controller.signal),
      getArchiveCards(deckUuid, 0, controller.signal),
    ])
      .then(([deck, cards]) => {
        if (!controller.signal.aborted) {
          setState({
            status: "success",
            deck,
            cards,
            error: null,
            isLoadingMore: false,
            loadMoreError: null,
          });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setState({ ...INITIAL_PREVIEW, status: "error", error });
      });
    return () => {
      controller.abort();
      moreControllerRef.current?.abort();
    };
  }, [deckUuid, revision]);

  const loadMore = useCallback(() => {
    if (
      state.status !== "success" ||
      state.deck === null ||
      state.isLoadingMore ||
      state.cards.length >= state.deck.wordsCount ||
      moreControllerRef.current !== null
    )
      return;

    const controller = new AbortController();
    moreControllerRef.current = controller;
    const offset = state.cards.length;
    setState((current) => ({ ...current, isLoadingMore: true, loadMoreError: null }));
    void getArchiveCards(deckUuid, offset, controller.signal)
      .then((cards) => {
        if (!controller.signal.aborted) {
          setState((current) => ({
            ...current,
            cards: [...current.cards, ...cards],
            isLoadingMore: false,
          }));
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState((current) => ({ ...current, isLoadingMore: false, loadMoreError: error }));
        }
      })
      .finally(() => {
        if (moreControllerRef.current === controller) moreControllerRef.current = null;
      });
  }, [deckUuid, state.cards.length, state.deck, state.isLoadingMore, state.status]);

  const retry = useCallback(() => setRevision((value) => value + 1), []);
  return {
    ...state,
    hasMore:
      state.deck !== null &&
      state.cards.length < state.deck.wordsCount &&
      state.cards.length > 0 &&
      state.cards.length % ARCHIVE_CARD_BATCH_SIZE === 0,
    retry,
    loadMore,
  };
}
