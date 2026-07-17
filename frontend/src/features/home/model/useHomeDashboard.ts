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

export function useHomeDashboard(): UseHomeDashboardResult {
  const [state, setState] = useState<HomeDashboardState>(INITIAL_STATE);
  const activeControllerRef = useRef<AbortController | null>(null);
  const requestRevisionRef = useRef(0);

  const load = useCallback((): void => {
    activeControllerRef.current?.abort();

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
          setState({ status: "success", data, error: null });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          setState({ status: "error", data: null, error });
        }
      })
      .finally(() => {
        if (activeControllerRef.current === controller) {
          activeControllerRef.current = null;
        }
      });
  }, []);

  useEffect(() => {
    load();

    return () => {
      requestRevisionRef.current += 1;
      activeControllerRef.current?.abort();
      activeControllerRef.current = null;
    };
  }, [load]);

  return { ...state, retry: load };
}
