import { useCallback, useEffect, useRef, useState } from "react";
import {
  resumePracticeSession,
  startPracticeSession,
  submitPracticeAnswer,
} from "../api/practice-api";
import type {
  CardSide,
  PracticeSession,
  SubmitPracticeAnswerInput,
  SubmitPracticeAnswerResult,
} from "./practice-types";
import { applyPracticeAnswerResult } from "./practice-session-state";

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
  start: (deckUuid: string, promptSide: CardSide) => Promise<PracticeSession | null>;
  submit: (
    sequenceNumber: number,
    input: SubmitPracticeAnswerInput,
  ) => Promise<SubmitPracticeAnswerResult | null>;
}

const IDLE_STATE: IdlePracticeState = { status: "idle" };

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
  const [state, setState] = useState<PracticeSessionState>(IDLE_STATE);
  const [resumeAttempt, setResumeAttempt] = useState(0);
  const loadControllerRef = useRef<AbortController | null>(null);
  const submitControllerRef = useRef<AbortController | null>(null);
  const loadRevisionRef = useRef(0);
  const sessionRef = useRef<PracticeSession | null>(null);
  const setupDeckUuidRef = useRef(setupDeckUuid);
  setupDeckUuidRef.current = setupDeckUuid;

  useEffect(() => {
    if (sessionUuid === null) {
      loadControllerRef.current?.abort();
      submitControllerRef.current?.abort();
      loadControllerRef.current = null;
      loadRevisionRef.current += 1;
      sessionRef.current = null;
      setState(IDLE_STATE);
      return;
    }

    if (sessionRef.current?.uuid === sessionUuid) {
      return;
    }

    loadControllerRef.current?.abort();
    submitControllerRef.current?.abort();

    const controller = new AbortController();
    const revision = loadRevisionRef.current + 1;
    loadRevisionRef.current = revision;
    loadControllerRef.current = controller;
    setState({ status: "loading", operation: "resume" });

    void resumePracticeSession(sessionUuid, controller.signal)
      .then((session) => {
        if (controller.signal.aborted || loadRevisionRef.current !== revision) {
          return;
        }

        sessionRef.current = session;
        setState(createReadyState(session));
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || loadRevisionRef.current !== revision) {
          return;
        }

        sessionRef.current = null;
        setState({ status: "error", operation: "resume", error });
      })
      .finally(() => {
        if (loadControllerRef.current === controller) {
          loadControllerRef.current = null;
        }
      });

    return () => {
      controller.abort();
    };
  }, [resumeAttempt, sessionUuid, setupDeckUuid]);

  useEffect(
    () => () => {
      loadControllerRef.current?.abort();
      submitControllerRef.current?.abort();
    },
    [],
  );

  const start = useCallback(
    async (deckUuid: string, promptSide: CardSide): Promise<PracticeSession | null> => {
      const normalizedDeckUuid = deckUuid.toLowerCase();
      if (setupDeckUuidRef.current?.toLowerCase() !== normalizedDeckUuid) {
        return null;
      }

      loadControllerRef.current?.abort();
      submitControllerRef.current?.abort();

      const controller = new AbortController();
      const revision = loadRevisionRef.current + 1;
      loadRevisionRef.current = revision;
      loadControllerRef.current = controller;
      sessionRef.current = null;
      setState({ status: "loading", operation: "start" });

      try {
        const session = await startPracticeSession(deckUuid, { promptSide }, controller.signal);
        if (
          controller.signal.aborted ||
          loadRevisionRef.current !== revision ||
          setupDeckUuidRef.current?.toLowerCase() !== normalizedDeckUuid
        ) {
          return null;
        }

        sessionRef.current = session;
        setState(createReadyState(session));
        return session;
      } catch (error: unknown) {
        if (
          controller.signal.aborted ||
          loadRevisionRef.current !== revision ||
          setupDeckUuidRef.current?.toLowerCase() !== normalizedDeckUuid
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
    [],
  );

  const submit = useCallback(
    async (
      sequenceNumber: number,
      input: SubmitPracticeAnswerInput,
    ): Promise<SubmitPracticeAnswerResult | null> => {
      const activeSession = sessionRef.current;
      if (activeSession === null) {
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
        if (controller.signal.aborted || sessionRef.current?.uuid !== activeSession.uuid) {
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
        setState((currentState) => {
          if (currentState.status !== "ready" || currentState.session.uuid !== activeSession.uuid) {
            return currentState;
          }

          return {
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
        });
        return result;
      } catch (error: unknown) {
        if (controller.signal.aborted || sessionRef.current?.uuid !== activeSession.uuid) {
          return null;
        }

        setState((currentState) =>
          currentState.status === "ready"
            ? {
                ...currentState,
                submittingSequenceNumber: null,
                submitError: { sequenceNumber, error },
              }
            : currentState,
        );
        return null;
      } finally {
        if (submitControllerRef.current === controller) {
          submitControllerRef.current = null;
        }
      }
    },
    [],
  );

  const retryResume = useCallback(() => {
    sessionRef.current = null;
    setResumeAttempt((attempt) => attempt + 1);
  }, []);

  return { state, retryResume, start, submit };
}
