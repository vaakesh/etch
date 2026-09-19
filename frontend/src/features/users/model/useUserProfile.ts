import { useCallback, useEffect, useRef, useState } from "react";
import { getUserProfile, getUserProfileDeckPage } from "../api/user-profile-api";
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
}

export interface UseUserProfileResult extends UserProfileState {
  retry: () => void;
  loadMore: () => void;
  setMockSaved: (deckUuid: string, value: boolean) => void;
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

  useEffect(() => {
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

  const setMockSaved = useCallback((deckUuid: string, value: boolean): void => {
    setState((currentState) => ({
      ...currentState,
      decks: currentState.decks.map((deck) =>
        deck.uuid === deckUuid ? { ...deck, isSaved: value } : deck,
      ),
    }));
  }, []);

  return { ...state, retry, loadMore, setMockSaved };
}
