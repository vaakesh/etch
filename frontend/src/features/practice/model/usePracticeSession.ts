import { useCallback, useEffect, useRef, useState } from "react";
import { useSessionCacheScope } from "../../../auth/hooks/useSessionCacheScope";
import {
  createSessionCacheKey,
  getSessionCacheEntry,
  isSessionCacheScopeActive,
  setSessionCacheEntry,
  type SessionCacheScope,
} from "../../../auth/model/session-cache";
import {
  resumePracticeSession,
  startPracticeSession,
  submitPracticeAnswer,
} from "../api/practice-api";
import { invalidatePracticeHistory } from "./practice-history-cache";
import { applyPracticeAnswerResult } from "./practice-session-state";
import type {
  CardSide,
  PracticeSession,
  SubmitPracticeAnswerInput,
  SubmitPracticeAnswerResult,
} from "./practice-types";

export interface PracticeCardFeedback {
  action: SubmitPracticeAnswerInput["action"];
  answerText: string;
  isCorrect: boolean;
  submittedAnswer: string | null;
}

interface IdlePracticeState {
  status: "idle";
}

interface LoadingPracticeState {
  status: "loading";
  operation: "resume" | "start";
}

interface ErrorPracticeState {
  status: "error";
  operation: "resume" | "start";
  error: unknown;
}

export interface ReadyPracticeState {
  status: "ready";
  session: PracticeSession;
  feedbackBySequence: Readonly<Record<number, PracticeCardFeedback>>;
  isFinished: boolean;
  timeToCompleteSeconds: number | null;
  submittingSequenceNumber: number | null;
  submitError: { sequenceNumber: number; error: unknown } | null;
}

export type PracticeSessionState =
  IdlePracticeState | LoadingPracticeState | ErrorPracticeState | ReadyPracticeState;

export interface UsePracticeSessionResult {
  state: PracticeSessionState;
  retryResume: () => void;
  start: (
    deckUuid: string,
    promptSide: CardSide,
    wordsPerSession: number,
  ) => Promise<PracticeSession | null>;
  submit: (
    sequenceNumber: number,
    input: SubmitPracticeAnswerInput,
  ) => Promise<SubmitPracticeAnswerResult | null>;
}

const IDLE_STATE: IdlePracticeState = { status: "idle" };
type PracticeSessionsCache = ReadonlyMap<string, PracticeSessionState>;
const PRACTICE_SESSIONS_CACHE_KEY =
  createSessionCacheKey<PracticeSessionsCache>("practice.sessions");

function setCachedPracticeSession(
  cacheScope: SessionCacheScope,
  sessionUuid: string,
  state: PracticeSessionState,
): boolean {
  const nextCache = new Map(getSessionCacheEntry(cacheScope, PRACTICE_SESSIONS_CACHE_KEY));
  nextCache.set(sessionUuid, state);
  return setSessionCacheEntry(cacheScope, PRACTICE_SESSIONS_CACHE_KEY, nextCache);
}

function deleteCachedPracticeSession(
  cacheScope: SessionCacheScope | null,
  sessionUuid: string,
): void {
  const cachedPracticeSessions = getSessionCacheEntry(cacheScope, PRACTICE_SESSIONS_CACHE_KEY);
  if (cachedPracticeSessions === undefined) {
    return;
  }

  const nextCache = new Map(cachedPracticeSessions);
  nextCache.delete(sessionUuid);
  setSessionCacheEntry(cacheScope, PRACTICE_SESSIONS_CACHE_KEY, nextCache);
}

function createReadyState(session: PracticeSession): ReadyPracticeState {
  return {
    status: "ready",
    session,
    feedbackBySequence: {},
    isFinished: false,
    timeToCompleteSeconds: null,
    submittingSequenceNumber: null,
    submitError: null,
  };
}

export function usePracticeSession(
  sessionUuid: string | null,
  setupDeckUuid: string | null,
): UsePracticeSessionResult {
  const cacheScope = useSessionCacheScope();
  const cachedPracticeSessions = getSessionCacheEntry(cacheScope, PRACTICE_SESSIONS_CACHE_KEY);
  const cachedStateAtMount =
    sessionUuid === null ? undefined : cachedPracticeSessions?.get(sessionUuid);
  const [state, setState] = useState<PracticeSessionState>(cachedStateAtMount ?? IDLE_STATE);
  const [stateScopeKey, setStateScopeKey] = useState<string | null>(
    cachedStateAtMount === undefined ? null : (cacheScope?.key ?? null),
  );
  const [resumeAttempt, setResumeAttempt] = useState(0);
  const loadControllerRef = useRef<AbortController | null>(null);
  const submitControllerRef = useRef<AbortController | null>(null);
  const activeResumeSessionUuidRef = useRef<string | null>(null);
  const cleanupTimerRef = useRef<number | null>(null);
  const loadRevisionRef = useRef(0);
  const sessionRef = useRef<PracticeSession | null>(
    cachedStateAtMount?.status === "ready" ? cachedStateAtMount.session : null,
  );
  const setupDeckUuidRef = useRef(setupDeckUuid);
  setupDeckUuidRef.current = setupDeckUuid;

  useEffect(() => {
    if (cleanupTimerRef.current !== null) {
      window.clearTimeout(cleanupTimerRef.current);
      cleanupTimerRef.current = null;
    }

    const scheduleCleanup = (): void => {
      cleanupTimerRef.current = window.setTimeout(() => {
        loadRevisionRef.current += 1;
        loadControllerRef.current?.abort();
        submitControllerRef.current?.abort();
        loadControllerRef.current = null;
        submitControllerRef.current = null;
        activeResumeSessionUuidRef.current = null;
        cleanupTimerRef.current = null;
      }, 0);
    };

    if (cacheScope === null) {
      loadRevisionRef.current += 1;
      loadControllerRef.current?.abort();
      submitControllerRef.current?.abort();
      loadControllerRef.current = null;
      submitControllerRef.current = null;
      activeResumeSessionUuidRef.current = null;
      sessionRef.current = null;
      queueMicrotask(() => {
        setStateScopeKey(null);
        setState(IDLE_STATE);
      });
      return scheduleCleanup;
    }

    if (sessionUuid === null) {
      loadRevisionRef.current += 1;
      loadControllerRef.current?.abort();
      submitControllerRef.current?.abort();
      loadControllerRef.current = null;
      submitControllerRef.current = null;
      activeResumeSessionUuidRef.current = null;
      sessionRef.current = null;
      queueMicrotask(() => setState(IDLE_STATE));
      return scheduleCleanup;
    }

    const cachedPracticeSessions = getSessionCacheEntry(cacheScope, PRACTICE_SESSIONS_CACHE_KEY);
    const cachedState = cachedPracticeSessions?.get(sessionUuid);
    if (cachedState !== undefined) {
      loadRevisionRef.current += 1;
      loadControllerRef.current?.abort();
      loadControllerRef.current = null;
      activeResumeSessionUuidRef.current = null;
      if (sessionRef.current?.uuid !== sessionUuid) {
        submitControllerRef.current?.abort();
        submitControllerRef.current = null;
      }
      sessionRef.current = cachedState.status === "ready" ? cachedState.session : null;
      queueMicrotask(() => {
        setStateScopeKey(cacheScope.key);
        setState(cachedState);
      });
      return scheduleCleanup;
    }

    if (loadControllerRef.current !== null && activeResumeSessionUuidRef.current === sessionUuid) {
      return scheduleCleanup;
    }

    loadControllerRef.current?.abort();
    submitControllerRef.current?.abort();

    const controller = new AbortController();
    const revision = loadRevisionRef.current + 1;
    loadRevisionRef.current = revision;
    loadControllerRef.current = controller;
    activeResumeSessionUuidRef.current = sessionUuid;
    queueMicrotask(() => {
      if (!controller.signal.aborted && loadRevisionRef.current === revision) {
        setStateScopeKey(cacheScope.key);
        setState({ status: "loading", operation: "resume" });
      }
    });

    void resumePracticeSession(sessionUuid, controller.signal)
      .then((session) => {
        if (
          controller.signal.aborted ||
          loadRevisionRef.current !== revision ||
          !isSessionCacheScopeActive(cacheScope)
        ) {
          return;
        }

        sessionRef.current = session;
        const nextState = createReadyState(session);
        if (setCachedPracticeSession(cacheScope, sessionUuid, nextState)) {
          setState(nextState);
        }
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          loadRevisionRef.current !== revision ||
          !isSessionCacheScopeActive(cacheScope)
        ) {
          return;
        }

        sessionRef.current = null;
        const nextState: PracticeSessionState = { status: "error", operation: "resume", error };
        if (setCachedPracticeSession(cacheScope, sessionUuid, nextState)) {
          setState(nextState);
        }
      })
      .finally(() => {
        if (loadControllerRef.current === controller) {
          loadControllerRef.current = null;
          activeResumeSessionUuidRef.current = null;
        }
      });

    return scheduleCleanup;
  }, [cacheScope, resumeAttempt, sessionUuid, setupDeckUuid]);

  const start = useCallback(
    async (
      deckUuid: string,
      promptSide: CardSide,
      wordsPerSession: number,
    ): Promise<PracticeSession | null> => {
      if (!isSessionCacheScopeActive(cacheScope)) {
        return null;
      }
      const normalizedDeckUuid = deckUuid.toLowerCase();
      if (
        setupDeckUuidRef.current !== null &&
        setupDeckUuidRef.current.toLowerCase() !== normalizedDeckUuid
      ) {
        return null;
      }

      loadControllerRef.current?.abort();
      submitControllerRef.current?.abort();
      activeResumeSessionUuidRef.current = null;

      const controller = new AbortController();
      const revision = loadRevisionRef.current + 1;
      loadRevisionRef.current = revision;
      loadControllerRef.current = controller;
      sessionRef.current = null;
      setStateScopeKey(cacheScope.key);
      setState({ status: "loading", operation: "start" });

      try {
        const session = await startPracticeSession(
          deckUuid,
          { promptSide, wordsPerSession },
          controller.signal,
        );
        if (
          controller.signal.aborted ||
          loadRevisionRef.current !== revision ||
          !isSessionCacheScopeActive(cacheScope) ||
          (setupDeckUuidRef.current !== null &&
            setupDeckUuidRef.current.toLowerCase() !== normalizedDeckUuid)
        ) {
          return null;
        }

        sessionRef.current = session;
        const nextState = createReadyState(session);
        setCachedPracticeSession(cacheScope, session.uuid, nextState);
        invalidatePracticeHistory(["all", "in_progress"]);
        setState(nextState);
        return session;
      } catch (error: unknown) {
        if (
          controller.signal.aborted ||
          loadRevisionRef.current !== revision ||
          !isSessionCacheScopeActive(cacheScope) ||
          (setupDeckUuidRef.current !== null &&
            setupDeckUuidRef.current.toLowerCase() !== normalizedDeckUuid)
        ) {
          return null;
        }

        setState({ status: "error", operation: "start", error });
        return null;
      } finally {
        if (loadControllerRef.current === controller) {
          loadControllerRef.current = null;
        }
      }
    },
    [cacheScope],
  );

  const submit = useCallback(
    async (
      sequenceNumber: number,
      input: SubmitPracticeAnswerInput,
    ): Promise<SubmitPracticeAnswerResult | null> => {
      const activeSession = sessionRef.current;
      if (activeSession === null || !isSessionCacheScopeActive(cacheScope)) {
        return null;
      }

      submitControllerRef.current?.abort();
      const controller = new AbortController();
      submitControllerRef.current = controller;

      setState((currentState) =>
        currentState.status === "ready"
          ? {
              ...currentState,
              submittingSequenceNumber: sequenceNumber,
              submitError: null,
            }
          : currentState,
      );

      try {
        const result = await submitPracticeAnswer(
          activeSession.uuid,
          sequenceNumber,
          input,
          controller.signal,
        );
        if (
          controller.signal.aborted ||
          sessionRef.current?.uuid !== activeSession.uuid ||
          !isSessionCacheScopeActive(cacheScope)
        ) {
          return null;
        }

        const nextSession = applyPracticeAnswerResult(activeSession, result);
        const feedback: PracticeCardFeedback = {
          action: input.action,
          answerText: result.answerText,
          isCorrect: result.isCorrect,
          submittedAnswer: input.action === "answer" ? input.answer.trim() : null,
        };

        sessionRef.current = nextSession;
        invalidatePracticeHistory(
          result.isFinished ? ["all", "in_progress", "completed"] : ["all", "in_progress"],
        );
        setState((currentState) => {
          if (currentState.status !== "ready" || currentState.session.uuid !== activeSession.uuid) {
            return currentState;
          }

          const nextState: ReadyPracticeState = {
            ...currentState,
            session: nextSession,
            feedbackBySequence: {
              ...currentState.feedbackBySequence,
              [sequenceNumber]: feedback,
            },
            isFinished: result.isFinished,
            timeToCompleteSeconds: result.timeToCompleteSeconds,
            submittingSequenceNumber: null,
            submitError: null,
          };
          setCachedPracticeSession(cacheScope, activeSession.uuid, nextState);
          return nextState;
        });
        return result;
      } catch (error: unknown) {
        if (
          controller.signal.aborted ||
          sessionRef.current?.uuid !== activeSession.uuid ||
          !isSessionCacheScopeActive(cacheScope)
        ) {
          return null;
        }

        setState((currentState) => {
          if (currentState.status !== "ready") {
            return currentState;
          }

          const nextState: ReadyPracticeState = {
            ...currentState,
            submittingSequenceNumber: null,
            submitError: { sequenceNumber, error },
          };
          setCachedPracticeSession(cacheScope, activeSession.uuid, nextState);
          return nextState;
        });
        return null;
      } finally {
        if (submitControllerRef.current === controller) {
          submitControllerRef.current = null;
        }
      }
    },
    [cacheScope],
  );

  const retryResume = useCallback(() => {
    if (sessionUuid !== null) {
      deleteCachedPracticeSession(cacheScope, sessionUuid);
    }
    sessionRef.current = null;
    setResumeAttempt((attempt) => attempt + 1);
  }, [cacheScope, sessionUuid]);

  const visibleState: PracticeSessionState =
    cacheScope !== null && stateScopeKey === cacheScope.key
      ? state
      : sessionUuid === null
        ? IDLE_STATE
        : { status: "loading", operation: "resume" };

  return { state: visibleState, retryResume, start, submit };
}
