import { useCallback, useEffect, useRef, useState } from "react";
import { useSessionCacheScope } from "../../../auth/hooks/useSessionCacheScope";
import {
  createSessionCacheKey,
  deleteSessionCacheEntry,
  getSessionCacheEntry,
  isSessionCacheScopeActive,
  setSessionCacheEntry,
} from "../../../auth/model/session-cache";
import { getHomeDashboard } from "../api/home-api";
import type { HomeDashboard } from "./home-types";

export type HomeDashboardStatus = "loading" | "success" | "error";

interface HomeDashboardState {
  status: HomeDashboardStatus;
  data: HomeDashboard | null;
  error: unknown | null;
}

interface UseHomeDashboardResult extends HomeDashboardState {
  retry: () => void;
}

const INITIAL_STATE: HomeDashboardState = {
  status: "loading",
  data: null,
  error: null,
};

const HOME_DASHBOARD_CACHE_KEY = createSessionCacheKey<HomeDashboardState>("home.dashboard");

export function useHomeDashboard(): UseHomeDashboardResult {
  const cacheScope = useSessionCacheScope();
  const cachedStateAtMount = getSessionCacheEntry(cacheScope, HOME_DASHBOARD_CACHE_KEY);
  const [state, setState] = useState<HomeDashboardState>(cachedStateAtMount ?? INITIAL_STATE);
  const [stateScopeKey, setStateScopeKey] = useState<string | null>(
    cachedStateAtMount === undefined ? null : (cacheScope?.key ?? null),
  );
  const activeControllerRef = useRef<AbortController | null>(null);
  const cleanupTimerRef = useRef<number | null>(null);
  const requestRevisionRef = useRef(0);

  const load = useCallback((): void => {
    activeControllerRef.current?.abort();

    if (!isSessionCacheScopeActive(cacheScope)) {
      requestRevisionRef.current += 1;
      activeControllerRef.current = null;
      setStateScopeKey(null);
      setState(INITIAL_STATE);
      return;
    }

    deleteSessionCacheEntry(cacheScope, HOME_DASHBOARD_CACHE_KEY);
    const controller = new AbortController();
    const requestRevision = requestRevisionRef.current + 1;
    requestRevisionRef.current = requestRevision;
    activeControllerRef.current = controller;
    queueMicrotask(() => {
      if (
        !controller.signal.aborted &&
        requestRevisionRef.current === requestRevision &&
        isSessionCacheScopeActive(cacheScope)
      ) {
        setStateScopeKey(cacheScope.key);
        setState(INITIAL_STATE);
      }
    });

    void getHomeDashboard(controller.signal)
      .then((data) => {
        const nextState: HomeDashboardState = { status: "success", data, error: null };
        if (
          !controller.signal.aborted &&
          requestRevisionRef.current === requestRevision &&
          setSessionCacheEntry(cacheScope, HOME_DASHBOARD_CACHE_KEY, nextState)
        ) {
          setState(nextState);
        }
      })
      .catch((error: unknown) => {
        const nextState: HomeDashboardState = { status: "error", data: null, error };
        if (
          !controller.signal.aborted &&
          requestRevisionRef.current === requestRevision &&
          setSessionCacheEntry(cacheScope, HOME_DASHBOARD_CACHE_KEY, nextState)
        ) {
          setState(nextState);
        }
      })
      .finally(() => {
        if (activeControllerRef.current === controller) {
          activeControllerRef.current = null;
        }
      });
  }, [cacheScope]);

  useEffect(() => {
    if (cleanupTimerRef.current !== null) {
      window.clearTimeout(cleanupTimerRef.current);
      cleanupTimerRef.current = null;
    }

    if (cacheScope === null) {
      requestRevisionRef.current += 1;
      activeControllerRef.current?.abort();
      activeControllerRef.current = null;
      queueMicrotask(() => {
        setStateScopeKey(null);
        setState(INITIAL_STATE);
      });
    } else {
      const cachedState = getSessionCacheEntry(cacheScope, HOME_DASHBOARD_CACHE_KEY);
      if (cachedState !== undefined) {
        queueMicrotask(() => {
          setStateScopeKey(cacheScope.key);
          setState(cachedState);
        });
      } else if (activeControllerRef.current === null || stateScopeKey !== cacheScope.key) {
        load();
      }
    }

    return () => {
      cleanupTimerRef.current = window.setTimeout(() => {
        requestRevisionRef.current += 1;
        activeControllerRef.current?.abort();
        activeControllerRef.current = null;
        cleanupTimerRef.current = null;
      }, 0);
    };
  }, [cacheScope, load, stateScopeKey]);

  const visibleState =
    cacheScope !== null && stateScopeKey === cacheScope.key ? state : INITIAL_STATE;

  return { ...visibleState, retry: load };
}
