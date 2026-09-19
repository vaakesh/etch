import { useCallback, useEffect, useRef, useState } from "react";
import { useSessionCacheScope } from "../../../auth/hooks/useSessionCacheScope";
import {
  createSessionCacheKey,
  getSessionCacheEntry,
  isSessionCacheScopeActive,
  setSessionCacheEntry,
} from "../../../auth/model/session-cache";
import { getPracticeSessionItemsHistory } from "../api/practice-api";
import type { PracticeSessionHistoryItem } from "./practice-types";

interface IdlePracticeSessionHistoryState {
  status: "idle";
}

interface LoadingPracticeSessionHistoryState {
  status: "loading";
  sessionUuid: string;
}

interface ReadyPracticeSessionHistoryState {
  status: "ready";
  sessionUuid: string;
  items: readonly PracticeSessionHistoryItem[];
}

interface ErrorPracticeSessionHistoryState {
  status: "error";
  sessionUuid: string;
  error: unknown;
}

export type PracticeSessionHistoryState =
  | IdlePracticeSessionHistoryState
  | LoadingPracticeSessionHistoryState
  | ReadyPracticeSessionHistoryState
  | ErrorPracticeSessionHistoryState;

export interface UsePracticeSessionHistoryResult {
  state: PracticeSessionHistoryState;
  retry: () => void;
}

const IDLE_STATE: IdlePracticeSessionHistoryState = { status: "idle" };
type PracticeSessionHistoryCache = ReadonlyMap<string, PracticeSessionHistoryState>;
const PRACTICE_SESSION_HISTORY_CACHE_KEY = createSessionCacheKey<PracticeSessionHistoryCache>(
  "practice.session-history",
);

export function usePracticeSessionHistory(
  sessionUuid: string | null,
): UsePracticeSessionHistoryResult {
  const cacheScope = useSessionCacheScope();
  const cachedSessionHistory = getSessionCacheEntry(cacheScope, PRACTICE_SESSION_HISTORY_CACHE_KEY);
  const cachedStateAtMount =
    sessionUuid === null ? undefined : cachedSessionHistory?.get(sessionUuid);
  const [state, setState] = useState<PracticeSessionHistoryState>(cachedStateAtMount ?? IDLE_STATE);
  const [stateScopeKey, setStateScopeKey] = useState<string | null>(
    cachedStateAtMount === undefined ? null : (cacheScope?.key ?? null),
  );
  const [attempt, setAttempt] = useState(0);
  const controllerRef = useRef<AbortController | null>(null);
  const activeSessionUuidRef = useRef<string | null>(null);
  const cleanupTimerRef = useRef<number | null>(null);
  const requestRevisionRef = useRef(0);

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
        activeSessionUuidRef.current = null;
        cleanupTimerRef.current = null;
      }, 0);
    };

    if (cacheScope === null) {
      requestRevisionRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
      activeSessionUuidRef.current = null;
      queueMicrotask(() => {
        setStateScopeKey(null);
        setState(IDLE_STATE);
      });
      return scheduleCleanup;
    }

    if (sessionUuid === null) {
      requestRevisionRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
      activeSessionUuidRef.current = null;
      return scheduleCleanup;
    }

    const cachedSessionHistory = getSessionCacheEntry(
      cacheScope,
      PRACTICE_SESSION_HISTORY_CACHE_KEY,
    );
    const cachedState = cachedSessionHistory?.get(sessionUuid);
    if (cachedState !== undefined) {
      if (activeSessionUuidRef.current !== null && activeSessionUuidRef.current !== sessionUuid) {
        requestRevisionRef.current += 1;
        controllerRef.current?.abort();
        controllerRef.current = null;
        activeSessionUuidRef.current = null;
      }
      queueMicrotask(() => {
        setStateScopeKey(cacheScope.key);
        setState(cachedState);
      });
      return scheduleCleanup;
    }

    if (controllerRef.current !== null && activeSessionUuidRef.current === sessionUuid) {
      return scheduleCleanup;
    }

    controllerRef.current?.abort();
    const controller = new AbortController();
    const requestRevision = requestRevisionRef.current + 1;
    requestRevisionRef.current = requestRevision;
    controllerRef.current = controller;
    activeSessionUuidRef.current = sessionUuid;

    queueMicrotask(() => {
      if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
        setStateScopeKey(cacheScope.key);
        setState({ status: "loading", sessionUuid });
      }
    });

    void getPracticeSessionItemsHistory(sessionUuid, controller.signal)
      .then((items) => {
        if (
          !controller.signal.aborted &&
          requestRevisionRef.current === requestRevision &&
          isSessionCacheScopeActive(cacheScope)
        ) {
          const nextState: PracticeSessionHistoryState = {
            status: "ready",
            sessionUuid,
            items,
          };
          const nextCache = new Map(
            getSessionCacheEntry(cacheScope, PRACTICE_SESSION_HISTORY_CACHE_KEY),
          );
          nextCache.set(sessionUuid, nextState);
          if (setSessionCacheEntry(cacheScope, PRACTICE_SESSION_HISTORY_CACHE_KEY, nextCache)) {
            setState(nextState);
          }
        }
      })
      .catch((error: unknown) => {
        if (
          !controller.signal.aborted &&
          requestRevisionRef.current === requestRevision &&
          isSessionCacheScopeActive(cacheScope)
        ) {
          const nextState: PracticeSessionHistoryState = {
            status: "error",
            sessionUuid,
            error,
          };
          const nextCache = new Map(
            getSessionCacheEntry(cacheScope, PRACTICE_SESSION_HISTORY_CACHE_KEY),
          );
          nextCache.set(sessionUuid, nextState);
          if (setSessionCacheEntry(cacheScope, PRACTICE_SESSION_HISTORY_CACHE_KEY, nextCache)) {
            setState(nextState);
          }
        }
      })
      .finally(() => {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
          activeSessionUuidRef.current = null;
        }
      });

    return scheduleCleanup;
  }, [attempt, cacheScope, sessionUuid]);

  const retry = useCallback(() => {
    if (sessionUuid !== null) {
      const cachedSessionHistory = getSessionCacheEntry(
        cacheScope,
        PRACTICE_SESSION_HISTORY_CACHE_KEY,
      );
      if (cachedSessionHistory !== undefined) {
        const nextCache = new Map(cachedSessionHistory);
        nextCache.delete(sessionUuid);
        setSessionCacheEntry(cacheScope, PRACTICE_SESSION_HISTORY_CACHE_KEY, nextCache);
      }
    }
    setAttempt((currentAttempt) => currentAttempt + 1);
  }, [cacheScope, sessionUuid]);

  const visibleState: PracticeSessionHistoryState =
    cacheScope === null || sessionUuid === null
      ? IDLE_STATE
      : stateScopeKey !== cacheScope.key ||
          state.status === "idle" ||
          state.sessionUuid !== sessionUuid
        ? { status: "loading", sessionUuid }
        : state;

  return { state: visibleState, retry };
}
