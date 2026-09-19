import { useCallback, useEffect, useRef, useState } from "react";
import { useSessionCacheScope } from "../../../auth/hooks/useSessionCacheScope";
import {
  createSessionCacheKey,
  getSessionCacheEntry,
  isSessionCacheScopeActive,
  setSessionCacheEntry,
} from "../../../auth/model/session-cache";
import { validatePracticeDeck } from "../api/practice-api";

interface IdlePracticeDeckState {
  status: "idle";
}

interface LoadingPracticeDeckState {
  status: "loading";
  deckUuid: string;
}

interface ReadyPracticeDeckState {
  status: "ready";
  deckUuid: string;
  wordsCount: number;
}

interface ErrorPracticeDeckState {
  status: "error";
  deckUuid: string;
  error: unknown;
}

export type PracticeDeckAvailabilityState =
  | IdlePracticeDeckState
  | LoadingPracticeDeckState
  | ReadyPracticeDeckState
  | ErrorPracticeDeckState;

export interface UsePracticeDeckAvailabilityResult {
  state: PracticeDeckAvailabilityState;
  retry: () => void;
}

const IDLE_STATE: IdlePracticeDeckState = { status: "idle" };
type PracticeDeckAvailabilityCache = ReadonlyMap<string, PracticeDeckAvailabilityState>;
const PRACTICE_DECK_AVAILABILITY_CACHE_KEY = createSessionCacheKey<PracticeDeckAvailabilityCache>(
  "practice.deck-availability",
);

export function usePracticeDeckAvailability(
  deckUuid: string | null,
): UsePracticeDeckAvailabilityResult {
  const cacheScope = useSessionCacheScope();
  const cachedPracticeDeckAvailability = getSessionCacheEntry(
    cacheScope,
    PRACTICE_DECK_AVAILABILITY_CACHE_KEY,
  );
  const cachedStateAtMount =
    deckUuid === null ? undefined : cachedPracticeDeckAvailability?.get(deckUuid);
  const [state, setState] = useState<PracticeDeckAvailabilityState>(
    cachedStateAtMount ?? IDLE_STATE,
  );
  const [stateScopeKey, setStateScopeKey] = useState<string | null>(
    cachedStateAtMount === undefined ? null : (cacheScope?.key ?? null),
  );
  const [attempt, setAttempt] = useState(0);
  const controllerRef = useRef<AbortController | null>(null);
  const activeDeckUuidRef = useRef<string | null>(null);
  const cleanupTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (cleanupTimerRef.current !== null) {
      window.clearTimeout(cleanupTimerRef.current);
      cleanupTimerRef.current = null;
    }

    const scheduleCleanup = (): void => {
      cleanupTimerRef.current = window.setTimeout(() => {
        controllerRef.current?.abort();
        controllerRef.current = null;
        activeDeckUuidRef.current = null;
        cleanupTimerRef.current = null;
      }, 0);
    };

    if (cacheScope === null) {
      controllerRef.current?.abort();
      controllerRef.current = null;
      activeDeckUuidRef.current = null;
      queueMicrotask(() => {
        setStateScopeKey(null);
        setState(IDLE_STATE);
      });
      return scheduleCleanup;
    }

    if (deckUuid === null) {
      controllerRef.current?.abort();
      controllerRef.current = null;
      activeDeckUuidRef.current = null;

      return scheduleCleanup;
    }

    const cachedPracticeDeckAvailability = getSessionCacheEntry(
      cacheScope,
      PRACTICE_DECK_AVAILABILITY_CACHE_KEY,
    );
    const cachedState = cachedPracticeDeckAvailability?.get(deckUuid);
    if (cachedState !== undefined) {
      if (activeDeckUuidRef.current !== null && activeDeckUuidRef.current !== deckUuid) {
        controllerRef.current?.abort();
        controllerRef.current = null;
        activeDeckUuidRef.current = null;
      }
      queueMicrotask(() => {
        setStateScopeKey(cacheScope.key);
        setState(cachedState);
      });

      return scheduleCleanup;
    }

    if (controllerRef.current !== null && activeDeckUuidRef.current === deckUuid) {
      return scheduleCleanup;
    }

    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    activeDeckUuidRef.current = deckUuid;
    queueMicrotask(() => {
      if (!controller.signal.aborted) {
        setStateScopeKey(cacheScope.key);
        setState({ status: "loading", deckUuid });
      }
    });

    void validatePracticeDeck(deckUuid, controller.signal)
      .then((deck) => {
        if (!controller.signal.aborted && isSessionCacheScopeActive(cacheScope)) {
          const nextState: PracticeDeckAvailabilityState = {
            status: "ready",
            deckUuid,
            wordsCount: deck.wordsCount,
          };
          const nextCache = new Map(
            getSessionCacheEntry(cacheScope, PRACTICE_DECK_AVAILABILITY_CACHE_KEY),
          );
          nextCache.set(deckUuid, nextState);
          if (setSessionCacheEntry(cacheScope, PRACTICE_DECK_AVAILABILITY_CACHE_KEY, nextCache)) {
            setState(nextState);
          }
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && isSessionCacheScopeActive(cacheScope)) {
          const nextState: PracticeDeckAvailabilityState = { status: "error", deckUuid, error };
          const nextCache = new Map(
            getSessionCacheEntry(cacheScope, PRACTICE_DECK_AVAILABILITY_CACHE_KEY),
          );
          nextCache.set(deckUuid, nextState);
          if (setSessionCacheEntry(cacheScope, PRACTICE_DECK_AVAILABILITY_CACHE_KEY, nextCache)) {
            setState(nextState);
          }
        }
      })
      .finally(() => {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
          activeDeckUuidRef.current = null;
        }
      });

    return scheduleCleanup;
  }, [attempt, cacheScope, deckUuid]);

  const retry = useCallback(() => {
    if (deckUuid !== null) {
      const cachedPracticeDeckAvailability = getSessionCacheEntry(
        cacheScope,
        PRACTICE_DECK_AVAILABILITY_CACHE_KEY,
      );
      if (cachedPracticeDeckAvailability !== undefined) {
        const nextCache = new Map(cachedPracticeDeckAvailability);
        nextCache.delete(deckUuid);
        setSessionCacheEntry(cacheScope, PRACTICE_DECK_AVAILABILITY_CACHE_KEY, nextCache);
      }
    }
    setAttempt((currentAttempt) => currentAttempt + 1);
  }, [cacheScope, deckUuid]);

  const visibleState: PracticeDeckAvailabilityState =
    cacheScope === null || deckUuid === null
      ? IDLE_STATE
      : stateScopeKey !== cacheScope.key || state.status === "idle" || state.deckUuid !== deckUuid
        ? { status: "loading", deckUuid }
        : state;

  return { state: visibleState, retry };
}
