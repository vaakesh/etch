import { useCallback, useEffect, useRef, useState } from "react";
import { useSessionCacheScope } from "../../../auth/hooks/useSessionCacheScope";
import {
  createSessionCacheKey,
  getSessionCacheEntry,
  isSessionCacheScopeActive,
  setSessionCacheEntry,
} from "../../../auth/model/session-cache";
import { getPracticeSessionHistory } from "../api/practice-api";
import {
  getPracticeHistoryInvalidationVersion,
  subscribeToPracticeHistoryInvalidation,
} from "./practice-history-cache";
import type { PracticeHistoryFilter, PracticeHistorySession } from "./practice-types";

interface LoadingPracticeHistoryState {
  status: "loading";
}

interface ReadyPracticeHistoryState {
  status: "ready";
  sessions: readonly PracticeHistorySession[];
}

interface ErrorPracticeHistoryState {
  status: "error";
  error: unknown;
}

export type PracticeHistoryState =
  LoadingPracticeHistoryState | ReadyPracticeHistoryState | ErrorPracticeHistoryState;

export interface UsePracticeHistoryResult {
  state: PracticeHistoryState;
  retry: () => void;
}

const LOADING_STATE: LoadingPracticeHistoryState = { status: "loading" };

interface FilteredPracticeHistoryState {
  filter: PracticeHistoryFilter;
  state: PracticeHistoryState;
}

interface CachedPracticeHistoryEntry {
  state: PracticeHistoryState;
  invalidationVersion: number;
}

type PracticeHistoryCache = ReadonlyMap<PracticeHistoryFilter, CachedPracticeHistoryEntry>;

const PRACTICE_HISTORY_CACHE_KEY = createSessionCacheKey<PracticeHistoryCache>("practice.history");

export function usePracticeHistory(filter: PracticeHistoryFilter): UsePracticeHistoryResult {
  const cacheScope = useSessionCacheScope();
  const cachedStateAtMount = getSessionCacheEntry(cacheScope, PRACTICE_HISTORY_CACHE_KEY)?.get(
    filter,
  )?.state;
  const [filteredState, setFilteredState] = useState<FilteredPracticeHistoryState>({
    filter,
    state: cachedStateAtMount ?? LOADING_STATE,
  });
  const [attempt, setAttempt] = useState(0);
  const [cacheRevision, setCacheRevision] = useState(0);
  const [stateScopeKey, setStateScopeKey] = useState<string | null>(
    cachedStateAtMount === undefined ? null : (cacheScope?.key ?? null),
  );
  const controllerRef = useRef<AbortController | null>(null);
  const activeFilterRef = useRef<PracticeHistoryFilter | null>(null);
  const activeInvalidationVersionRef = useRef<number | null>(null);
  const cleanupTimerRef = useRef<number | null>(null);
  const requestRevisionRef = useRef(0);

  useEffect(
    () =>
      subscribeToPracticeHistoryInvalidation(filter, () => {
        setCacheRevision((currentRevision) => currentRevision + 1);
      }),
    [filter],
  );

  useEffect(() => {
    if (cleanupTimerRef.current !== null) {
      window.clearTimeout(cleanupTimerRef.current);
      cleanupTimerRef.current = null;
    }

    const scheduleCleanup = (): void => {
      cleanupTimerRef.current = window.setTimeout(() => {
        requestRevisionRef.current += 1;
        controllerRef.current?.abort();
        controllerRef.current = null;
        activeFilterRef.current = null;
        activeInvalidationVersionRef.current = null;
        cleanupTimerRef.current = null;
      }, 0);
    };

    if (cacheScope === null) {
      requestRevisionRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
      activeFilterRef.current = null;
      activeInvalidationVersionRef.current = null;
      queueMicrotask(() => {
        setStateScopeKey(null);
        setFilteredState({ filter, state: LOADING_STATE });
      });
      return scheduleCleanup;
    }

    const invalidationVersion = getPracticeHistoryInvalidationVersion(filter);
    const cachedPracticeHistory = getSessionCacheEntry(cacheScope, PRACTICE_HISTORY_CACHE_KEY);
    const cachedEntry = cachedPracticeHistory?.get(filter);
    if (cachedEntry !== undefined && cachedEntry.invalidationVersion === invalidationVersion) {
      if (activeFilterRef.current !== null && activeFilterRef.current !== filter) {
        requestRevisionRef.current += 1;
        controllerRef.current?.abort();
        controllerRef.current = null;
        activeFilterRef.current = null;
        activeInvalidationVersionRef.current = null;
      }
      queueMicrotask(() => {
        setStateScopeKey(cacheScope.key);
        setFilteredState({ filter, state: cachedEntry.state });
      });

      return scheduleCleanup;
    }

    if (
      controllerRef.current !== null &&
      activeFilterRef.current === filter &&
      activeInvalidationVersionRef.current === invalidationVersion
    ) {
      return scheduleCleanup;
    }

    controllerRef.current?.abort();

    const controller = new AbortController();
    const requestRevision = requestRevisionRef.current + 1;
    requestRevisionRef.current = requestRevision;
    controllerRef.current = controller;
    activeFilterRef.current = filter;
    activeInvalidationVersionRef.current = invalidationVersion;

    const preservedState = cachedEntry?.state.status === "ready" ? cachedEntry.state : undefined;

    queueMicrotask(() => {
      if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
        setStateScopeKey(cacheScope.key);
        setFilteredState({ filter, state: preservedState ?? LOADING_STATE });
      }
    });

    void getPracticeSessionHistory(filter, controller.signal)
      .then((sessions) => {
        if (
          !controller.signal.aborted &&
          requestRevisionRef.current === requestRevision &&
          getPracticeHistoryInvalidationVersion(filter) === invalidationVersion &&
          isSessionCacheScopeActive(cacheScope)
        ) {
          const nextState: PracticeHistoryState = { status: "ready", sessions };
          const nextCache = new Map(getSessionCacheEntry(cacheScope, PRACTICE_HISTORY_CACHE_KEY));
          nextCache.set(filter, { state: nextState, invalidationVersion });
          if (setSessionCacheEntry(cacheScope, PRACTICE_HISTORY_CACHE_KEY, nextCache)) {
            setFilteredState({ filter, state: nextState });
          }
        }
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          requestRevisionRef.current !== requestRevision ||
          getPracticeHistoryInvalidationVersion(filter) !== invalidationVersion ||
          !isSessionCacheScopeActive(cacheScope)
        ) {
          return;
        }

        if (preservedState !== undefined) {
          setFilteredState({ filter, state: preservedState });
        } else {
          const nextState: PracticeHistoryState = { status: "error", error };
          const nextCache = new Map(getSessionCacheEntry(cacheScope, PRACTICE_HISTORY_CACHE_KEY));
          nextCache.set(filter, { state: nextState, invalidationVersion });
          if (setSessionCacheEntry(cacheScope, PRACTICE_HISTORY_CACHE_KEY, nextCache)) {
            setFilteredState({ filter, state: nextState });
          }
        }
      })
      .finally(() => {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
          activeFilterRef.current = null;
          activeInvalidationVersionRef.current = null;
        }
      });

    return scheduleCleanup;
  }, [attempt, cacheRevision, cacheScope, filter]);

  const retry = useCallback(() => {
    const cachedPracticeHistory = getSessionCacheEntry(cacheScope, PRACTICE_HISTORY_CACHE_KEY);
    if (cachedPracticeHistory !== undefined) {
      const nextCache = new Map(cachedPracticeHistory);
      nextCache.delete(filter);
      setSessionCacheEntry(cacheScope, PRACTICE_HISTORY_CACHE_KEY, nextCache);
    }
    setAttempt((currentAttempt) => currentAttempt + 1);
  }, [cacheScope, filter]);

  return {
    state:
      cacheScope !== null && stateScopeKey === cacheScope.key && filteredState.filter === filter
        ? filteredState.state
        : LOADING_STATE,
    retry,
  };
}
