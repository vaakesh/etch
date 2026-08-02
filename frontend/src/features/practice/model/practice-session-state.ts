import { ApiError } from "../../../api";
import type { PracticeSession, SubmitPracticeAnswerResult } from "./practice-types";

function invalidPracticeTransition(message: string): never {
  throw new ApiError({
    status: 0,
    code: "INVALID_PRACTICE_RESPONSE",
    message,
  });
}

export function applyPracticeAnswerResult(
  session: PracticeSession,
  result: SubmitPracticeAnswerResult,
): PracticeSession {
  const nextWrongCount = result.answeredCount - result.correctCount;

  if (result.totalCount !== session.totalCount) {
    return invalidPracticeTransition(
      "The backend returned answer counters for a different practice session.",
    );
  }
  if (
    result.answeredCount < session.answeredCount ||
    result.correctCount < session.correctCount ||
    nextWrongCount < session.wrongCount
  ) {
    return invalidPracticeTransition("The backend returned regressing practice counters.");
  }

  return {
    ...session,
    answeredCount: result.answeredCount,
    correctCount: result.correctCount,
    wrongCount: nextWrongCount,
  };
}
