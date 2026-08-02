import { describe, expect, it } from "vitest";
import type { PracticeSession, SubmitPracticeAnswerResult } from "./practice-types";
import { applyPracticeAnswerResult } from "./practice-session-state";

const SESSION: PracticeSession = {
  uuid: "019c05e5-bc86-70e6-8f5c-d31bfa1aac10",
  deckUuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
  promptSide: "front",
  answerSide: "back",
  totalCount: 4,
  answeredCount: 1,
  correctCount: 1,
  wrongCount: 0,
  startedAt: "2026-08-01T10:15:30Z",
  cards: [],
};

const RESULT: SubmitPracticeAnswerResult = {
  isCorrect: false,
  answerText: "спасибо",
  answeredCount: 2,
  correctCount: 1,
  totalCount: 4,
  isFinished: false,
  timeToCompleteSeconds: null,
};

describe("applyPracticeAnswerResult", () => {
  it("merges server counters and derives the missing wrong count", () => {
    expect(applyPracticeAnswerResult(SESSION, RESULT)).toMatchObject({
      totalCount: 4,
      answeredCount: 2,
      correctCount: 1,
      wrongCount: 1,
    });
  });

  it("accepts monotonic jumps caused by another tab answering the same session", () => {
    expect(
      applyPracticeAnswerResult(SESSION, {
        ...RESULT,
        answeredCount: 4,
        correctCount: 3,
        isCorrect: true,
        isFinished: true,
        timeToCompleteSeconds: 48,
      }),
    ).toMatchObject({ answeredCount: 4, correctCount: 3, wrongCount: 1 });
  });

  it("rejects a different total or counters that move backwards", () => {
    expect(() => applyPracticeAnswerResult(SESSION, { ...RESULT, totalCount: 5 })).toThrow();
    expect(() =>
      applyPracticeAnswerResult(SESSION, {
        ...RESULT,
        answeredCount: 1,
        correctCount: 0,
      }),
    ).toThrow();
    expect(() =>
      applyPracticeAnswerResult(
        { ...SESSION, answeredCount: 2, correctCount: 1, wrongCount: 1 },
        { ...RESULT, correctCount: 2 },
      ),
    ).toThrow();
  });
});
