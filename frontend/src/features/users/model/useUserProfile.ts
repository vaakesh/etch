import { useCallback, useEffect, useRef, useState } from "react";
import { getUserProfile, getUserProfileDeckPage } from "../api/user-profile-api";
import { setCatalogDeckSaved } from "../../catalog/api/catalog-api";
import type { UserProfile, UserProfileDeck } from "./user-profile-types";

export type UserProfileStatus = "loading" | "success" | "error";

interface UserProfileState {
  status: UserProfileStatus;
  profile: UserProfile | null;
  decks: readonly UserProfileDeck[];
  nextCursor: string | null;
  hasMore: boolean;
  error: unknown | null;
  isLoadingMore: boolean;
  loadMoreError: unknown | null;
  savingDeckUuids: readonly string[];
  saveErrors: Readonly<Record<string, unknown>>;
}

export interface UseUserProfileResult extends UserProfileState {
  retry: () => void;
  loadMore: () => void;
  setSaved: (deckUuid: string, value: boolean) => void;
}

const INITIAL_STATE: UserProfileState = {
  status: "loading",
  profile: null,
  decks: [],
  nextCursor: null,
  hasMore: false,
  error: null,
  isLoadingMore: false,
  loadMoreError: null,
  savingDeckUuids: [],
  saveErrors: {},
};

function appendUniqueDecks(
  currentDecks: readonly UserProfileDeck[],
  nextDecks: readonly UserProfileDeck[],
): readonly UserProfileDeck[] {
  const knownDeckUuids = new Set(currentDecks.map((deck) => deck.uuid));
  return [...currentDecks, ...nextDecks.filter((deck) => !knownDeckUuids.has(deck.uuid))];
}

export function useUserProfile(username: string): UseUserProfileResult {
  const [state, setState] = useState<UserProfileState>(INITIAL_STATE);
  const [retryRevision, setRetryRevision] = useState(0);
  const initialControllerRef = useRef<AbortController | null>(null);
  const loadMoreControllerRef = useRef<AbortController | null>(null);
  const requestRevisionRef = useRef(0);
  const saveControllerRefs = useRef(new Map<string, AbortController>());

  useEffect(() => {
    const saveControllers = saveControllerRefs.current;
    saveControllers.forEach((saveController) => saveController.abort());
    saveControllers.clear();
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

    void getUserProfile(username, controller.signal)
      .then(async (profile) => {
        const page = await getUserProfileDeckPage(profile.uuid, null, controller.signal);
        return { profile, page };
      })
      .then(({ page, profile }) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState({
            ...INITIAL_STATE,
            status: "success",
            profile,
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
          setState({ ...INITIAL_STATE, status: "error", error });
        }
      })
      .finally(() => {
        if (initialControllerRef.current === controller) {
          initialControllerRef.current = null;
        }
      });

    return () => {
      requestRevisionRef.current += 1;
      controller.abort();
      saveControllers.forEach((saveController) => saveController.abort());
      saveControllers.clear();
      loadMoreControllerRef.current?.abort();
      loadMoreControllerRef.current = null;
    };
  }, [retryRevision, username]);

  const retry = useCallback((): void => {
    setRetryRevision((revision) => revision + 1);
  }, []);

  const loadMore = useCallback((): void => {
    if (
      state.status !== "success" ||
      state.profile === null ||
      state.isLoadingMore ||
      !state.hasMore ||
      state.nextCursor === null ||
      loadMoreControllerRef.current !== null
    ) {
      return;
    }

    const controller = new AbortController();
    const requestRevision = requestRevisionRef.current;
    const cursor = state.nextCursor;
    const userUuid = state.profile.uuid;
    loadMoreControllerRef.current = controller;
    setState((currentState) => ({
      ...currentState,
      isLoadingMore: true,
      loadMoreError: null,
    }));

    void getUserProfileDeckPage(userUuid, cursor, controller.signal)
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
  }, [state.hasMore, state.isLoadingMore, state.nextCursor, state.profile, state.status]);

  const setSaved = useCallback(
    (deckUuid: string, value: boolean): void => {
      const deck = state.decks.find((candidate) => candidate.uuid === deckUuid);
      if (
        state.status !== "success" ||
        deck === undefined ||
        deck.isSaved === value ||
        saveControllerRefs.current.has(deckUuid)
      ) {
        return;
      }

      const controller = new AbortController();
      const requestRevision = requestRevisionRef.current;
      saveControllerRefs.current.set(deckUuid, controller);
      setState((currentState) => {
        const saveErrors = { ...currentState.saveErrors };
        delete saveErrors[deckUuid];
        return {
          ...currentState,
          savingDeckUuids: [...currentState.savingDeckUuids, deckUuid],
          saveErrors,
        };
      });

      void setCatalogDeckSaved(deckUuid, value, controller.signal)
        .then(() => {
          if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
            setState((currentState) => ({
              ...currentState,
              decks: currentState.decks.map((candidate) =>
                candidate.uuid === deckUuid ? { ...candidate, isSaved: value } : candidate,
              ),
              savingDeckUuids: currentState.savingDeckUuids.filter((uuid) => uuid !== deckUuid),
            }));
          }
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
            setState((currentState) => ({
              ...currentState,
              savingDeckUuids: currentState.savingDeckUuids.filter((uuid) => uuid !== deckUuid),
              saveErrors: { ...currentState.saveErrors, [deckUuid]: error },
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

  return { ...state, retry, loadMore, setSaved };
}
