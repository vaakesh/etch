import { useCallback, useEffect, useRef, useState } from "react";
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

let cachedHomeDashboardState: HomeDashboardState | null = null;

export function useHomeDashboard(): UseHomeDashboardResult {
  const cachedStateAtMount = cachedHomeDashboardState;
  const shouldLoadOnMountRef = useRef(cachedStateAtMount === null);
  const [state, setState] = useState<HomeDashboardState>(cachedStateAtMount ?? INITIAL_STATE);
  const activeControllerRef = useRef<AbortController | null>(null);
  const cleanupTimerRef = useRef<number | null>(null);
  const requestRevisionRef = useRef(0);

  const load = useCallback((): void => {
    activeControllerRef.current?.abort();
    cachedHomeDashboardState = null;

    const controller = new AbortController();
    const requestRevision = requestRevisionRef.current + 1;
    requestRevisionRef.current = requestRevision;
    activeControllerRef.current = controller;
    queueMicrotask(() => {
      if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
        setState(INITIAL_STATE);
      }
    });

    void getHomeDashboard(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          const nextState: HomeDashboardState = { status: "success", data, error: null };
          cachedHomeDashboardState = nextState;
          setState(nextState);
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          const nextState: HomeDashboardState = { status: "error", data: null, error };
          cachedHomeDashboardState = nextState;
          setState(nextState);
        }
      })
      .finally(() => {
        if (activeControllerRef.current === controller) {
          activeControllerRef.current = null;
        }
      });
  }, []);

  useEffect(() => {
    if (cleanupTimerRef.current !== null) {
      window.clearTimeout(cleanupTimerRef.current);
      cleanupTimerRef.current = null;
    }

    if (shouldLoadOnMountRef.current) {
      shouldLoadOnMountRef.current = false;
      load();
    }

    return () => {
      cleanupTimerRef.current = window.setTimeout(() => {
        requestRevisionRef.current += 1;
        activeControllerRef.current?.abort();
        activeControllerRef.current = null;
        cleanupTimerRef.current = null;
      }, 0);
    };
  }, [load]);

  return { ...state, retry: load };
}
