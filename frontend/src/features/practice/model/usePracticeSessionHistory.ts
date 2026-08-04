import { useCallback, useEffect, useRef, useState } from "react";
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
const cachedSessionHistory = new Map<string, PracticeSessionHistoryState>();

export function usePracticeSessionHistory(
  sessionUuid: string | null,
): UsePracticeSessionHistoryResult {
  const cachedStateAtMount =
    sessionUuid === null ? undefined : cachedSessionHistory.get(sessionUuid);
  const [state, setState] = useState<PracticeSessionHistoryState>(cachedStateAtMount ?? IDLE_STATE);
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

    if (sessionUuid === null) {
      requestRevisionRef.current += 1;
      controllerRef.current?.abort();
      controllerRef.current = null;
      activeSessionUuidRef.current = null;
      return scheduleCleanup;
    }

    const cachedState = cachedSessionHistory.get(sessionUuid);
    if (cachedState !== undefined) {
      if (activeSessionUuidRef.current !== null && activeSessionUuidRef.current !== sessionUuid) {
        requestRevisionRef.current += 1;
        controllerRef.current?.abort();
        controllerRef.current = null;
        activeSessionUuidRef.current = null;
      }
      queueMicrotask(() => setState(cachedState));
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
        setState({ status: "loading", sessionUuid });
      }
    });

    void getPracticeSessionItemsHistory(sessionUuid, controller.signal)
      .then((items) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          const nextState: PracticeSessionHistoryState = {
            status: "ready",
            sessionUuid,
            items,
          };
          cachedSessionHistory.set(sessionUuid, nextState);
          setState(nextState);
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && requestRevisionRef.current === requestRevision) {
          const nextState: PracticeSessionHistoryState = {
            status: "error",
            sessionUuid,
            error,
          };
          cachedSessionHistory.set(sessionUuid, nextState);
          setState(nextState);
        }
      })
      .finally(() => {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
          activeSessionUuidRef.current = null;
        }
      });

    return scheduleCleanup;
  }, [attempt, sessionUuid]);

  const retry = useCallback(() => {
    if (sessionUuid !== null) {
      cachedSessionHistory.delete(sessionUuid);
    }
    setAttempt((currentAttempt) => currentAttempt + 1);
  }, [sessionUuid]);

  const visibleState: PracticeSessionHistoryState =
    sessionUuid === null
      ? IDLE_STATE
      : state.status === "idle" || state.sessionUuid !== sessionUuid
        ? { status: "loading", sessionUuid }
        : state;

  return { state: visibleState, retry };
}
