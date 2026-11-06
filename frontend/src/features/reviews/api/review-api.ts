import { ApiError, apiFetch } from "../../../api";
import { parsePracticeSession } from "../../practice/model/practice-contract";
import type { CardSide, PracticeSession } from "../../practice/model/practice-types";
import { parseReviewSummary } from "../model/review-contract";
import type { ReviewSummary } from "../model/review-types";

export async function getReviewSummary(signal?: AbortSignal): Promise<ReviewSummary> {
  const payload = await apiFetch<unknown>("/bff/reviews/summary", { signal });
  return parseReviewSummary(payload);
}

export interface StartReviewSessionInput {
  promptSide: CardSide;
  wordsPerSession: number;
}

export async function startReviewSession(
  input: StartReviewSessionInput,
  signal?: AbortSignal,
): Promise<PracticeSession> {
  const payload = await apiFetch<unknown>("/bff/reviews/start", {
    method: "POST",
    body: {
      prompt_side: input.promptSide,
      words_per_session: input.wordsPerSession,
    },
    signal,
  });
  const session = parsePracticeSession(payload);

  // Сессия повторения собирает слова из разных колод, поэтому колоды у неё нет
  if (
    session.deckUuid !== null ||
    session.promptSide !== input.promptSide ||
    session.totalCount > input.wordsPerSession ||
    session.answeredCount !== 0 ||
    session.cards.length === 0
  ) {
    throw new ApiError({
      status: 0,
      code: "INVALID_REVIEW_RESPONSE",
      message: "The backend returned an unexpected newly started review session.",
    });
  }
  return session;
}
