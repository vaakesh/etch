import { useCallback, useEffect, useRef, useState } from "react";
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
const cachedPracticeDeckAvailability = new Map<string, PracticeDeckAvailabilityState>();

export function usePracticeDeckAvailability(
  deckUuid: string | null,
): UsePracticeDeckAvailabilityResult {
  const cachedStateAtMount =
    deckUuid === null ? undefined : cachedPracticeDeckAvailability.get(deckUuid);
  const [state, setState] = useState<PracticeDeckAvailabilityState>(
    cachedStateAtMount ?? IDLE_STATE,
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

    if (deckUuid === null) {
      controllerRef.current?.abort();
      controllerRef.current = null;
      activeDeckUuidRef.current = null;

      return scheduleCleanup;
    }

    const cachedState = cachedPracticeDeckAvailability.get(deckUuid);
    if (cachedState !== undefined) {
      if (activeDeckUuidRef.current !== null && activeDeckUuidRef.current !== deckUuid) {
        controllerRef.current?.abort();
        controllerRef.current = null;
        activeDeckUuidRef.current = null;
      }
      queueMicrotask(() => setState(cachedState));

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
        setState({ status: "loading", deckUuid });
      }
    });

    void validatePracticeDeck(deckUuid, controller.signal)
      .then(() => {
        if (!controller.signal.aborted) {
          const nextState: PracticeDeckAvailabilityState = { status: "ready", deckUuid };
          cachedPracticeDeckAvailability.set(deckUuid, nextState);
          setState(nextState);
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          const nextState: PracticeDeckAvailabilityState = { status: "error", deckUuid, error };
          cachedPracticeDeckAvailability.set(deckUuid, nextState);
          setState(nextState);
        }
      })
      .finally(() => {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
          activeDeckUuidRef.current = null;
        }
      });

    return scheduleCleanup;
  }, [attempt, deckUuid]);

  const retry = useCallback(() => {
    if (deckUuid !== null) {
      cachedPracticeDeckAvailability.delete(deckUuid);
    }
    setAttempt((currentAttempt) => currentAttempt + 1);
  }, [deckUuid]);

  const visibleState: PracticeDeckAvailabilityState =
    deckUuid === null
      ? IDLE_STATE
      : state.status === "idle" || state.deckUuid !== deckUuid
        ? { status: "loading", deckUuid }
        : state;

  return { state: visibleState, retry };
}
