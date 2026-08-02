import { ApiError, apiFetch } from "../../../api";
import { parsePracticeSession, parseSubmitPracticeAnswerResult } from "../model/practice-contract";
import type {
  PracticeSession,
  StartPracticeSessionInput,
  SubmitPracticeAnswerInput,
  SubmitPracticeAnswerResult,
} from "../model/practice-types";

function assertExpectedUuid(expectedUuid: string, actualUuid: string, resource: string): void {
  if (actualUuid.toLowerCase() !== expectedUuid.toLowerCase()) {
    throw new ApiError({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
      message: `The backend returned ${resource} with an unexpected UUID.`,
    });
  }
}

export async function startPracticeSession(
  deckUuid: string,
  input: StartPracticeSessionInput,
  signal?: AbortSignal,
): Promise<PracticeSession> {
  const payload = await apiFetch<unknown>(`/bff/practice/${deckUuid}/start`, {
    method: "POST",
    body: { prompt_side: input.promptSide },
    signal,
  });
  const session = parsePracticeSession(payload);

  assertExpectedUuid(deckUuid, session.deckUuid, "a practice session for a different deck");
  if (
    session.promptSide !== input.promptSide ||
    session.answeredCount !== 0 ||
    session.correctCount !== 0 ||
    session.wrongCount !== 0
  ) {
    throw new ApiError({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
      message: "The backend returned an unexpected newly started practice session.",
    });
  }
  return session;
}

export async function resumePracticeSession(
  sessionUuid: string,
  signal?: AbortSignal,
): Promise<PracticeSession> {
  const payload = await apiFetch<unknown>(`/bff/practice/${sessionUuid}/resume`, { signal });
  const session = parsePracticeSession(payload);

  assertExpectedUuid(sessionUuid, session.uuid, "a different practice session");
  if (session.answeredCount >= session.totalCount || session.cards.length === 0) {
    throw new ApiError({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
      message: "The backend returned a finished practice session from the resume endpoint.",
    });
  }
  return session;
}

export async function submitPracticeAnswer(
  sessionUuid: string,
  sequenceNumber: number,
  input: SubmitPracticeAnswerInput,
  signal?: AbortSignal,
): Promise<SubmitPracticeAnswerResult> {
  const body =
    input.action === "answer"
      ? { action: input.action, answer: input.answer }
      : { action: input.action };
  const payload = await apiFetch<unknown>(
    `/training-sessions/${sessionUuid}/items/${sequenceNumber}/submit`,
    {
      method: "PUT",
      body,
      signal,
    },
  );

  return parseSubmitPracticeAnswerResult(payload);
}
