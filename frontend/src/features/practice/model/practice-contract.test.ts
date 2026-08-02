import { describe, expect, it } from "vitest";
import { isApiError } from "../../../api";
import { parsePracticeSession, parseSubmitPracticeAnswerResult } from "./practice-contract";

const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const SESSION_UUID = "019c05e5-bc86-70e6-8f5c-d31bfa1aac10";

const VALID_SESSION = {
  training_session_uuid: SESSION_UUID,
  deck_uuid: DECK_UUID,
  prompt_side: "front",
  answer_side: "back",
  total_count: 3,
  answered_count: 1,
  correct_count: 1,
  wrong_count: 0,
  started_at: "2026-08-01T10:15:30.123456+00:00",
  cards: [
    {
      sequence_number: 2,
      prompt_text: "merci",
      prompt_language: "fr",
      answer_language: "ru",
    },
    {
      sequence_number: 3,
      prompt_text: "bonjour",
      prompt_language: "fr",
      answer_language: "ru",
    },
  ],
};

const VALID_ANSWER_RESULT = {
  is_correct: false,
  answer_text: "спасибо",
  answered_count: 2,
  correct_count: 1,
  total_count: 3,
  is_finished: false,
  time_to_complete: null,
};

function expectInvalidPracticeResponse(run: () => unknown): void {
  try {
    run();
    expect.fail("Expected a practice contract error.");
  } catch (error) {
    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error).toMatchObject({ status: 0, code: "INVALID_PRACTICE_RESPONSE" });
    }
  }
}

describe("parsePracticeSession", () => {
  it("maps the BFF session and preserves unanswered sequence numbers", () => {
    expect(parsePracticeSession(VALID_SESSION)).toEqual({
      uuid: SESSION_UUID,
      deckUuid: DECK_UUID,
      promptSide: "front",
      answerSide: "back",
      totalCount: 3,
      answeredCount: 1,
      correctCount: 1,
      wrongCount: 0,
      startedAt: "2026-08-01T10:15:30.123456+00:00",
      cards: [
        {
          sequenceNumber: 2,
          promptText: "merci",
          promptLanguage: "fr",
          answerLanguage: "ru",
        },
        {
          sequenceNumber: 3,
          promptText: "bonjour",
          promptLanguage: "fr",
          answerLanguage: "ru",
        },
      ],
    });
  });

  it.each([
    ["malformed session UUID", { training_session_uuid: "not-a-uuid" }],
    ["malformed deck UUID", { deck_uuid: "not-a-uuid" }],
    ["malformed date-time", { started_at: "2026-02-30T10:15:30Z" }],
    ["non-integer count", { total_count: 3.5 }],
    [
      "non-string prompt",
      { cards: [{ ...VALID_SESSION.cards[0], prompt_text: null }, VALID_SESSION.cards[1]] },
    ],
  ])("rejects %s", (_caseName, override) => {
    expectInvalidPracticeResponse(() => parsePracticeSession({ ...VALID_SESSION, ...override }));
  });

  it.each([
    ["zero total", { total_count: 0, answered_count: 0, correct_count: 0, cards: [] }],
    ["too many answers", { answered_count: 4, correct_count: 1, wrong_count: 3, cards: [] }],
    ["negative correct count", { correct_count: -1, wrong_count: 2 }],
    ["counter sum mismatch", { correct_count: 0, wrong_count: 0 }],
    ["non-opposite sides", { answer_side: "front" }],
    ["inconsistent remaining cards", { cards: [VALID_SESSION.cards[0]] }],
  ])("rejects the %s invariant", (_caseName, override) => {
    expectInvalidPracticeResponse(() => parsePracticeSession({ ...VALID_SESSION, ...override }));
  });

  it("accepts sparse original deck positions even when a number exceeds total_count", () => {
    expect(
      parsePracticeSession({
        ...VALID_SESSION,
        cards: [VALID_SESSION.cards[0], { ...VALID_SESSION.cards[1], sequence_number: 7 }],
      }),
    ).toMatchObject({ cards: [{ sequenceNumber: 2 }, { sequenceNumber: 7 }] });
  });

  it("rejects duplicate, non-positive, and unsorted card sequence numbers", () => {
    expectInvalidPracticeResponse(() =>
      parsePracticeSession({
        ...VALID_SESSION,
        cards: [VALID_SESSION.cards[0], { ...VALID_SESSION.cards[1], sequence_number: 2 }],
      }),
    );

    expectInvalidPracticeResponse(() =>
      parsePracticeSession({
        ...VALID_SESSION,
        cards: [VALID_SESSION.cards[0], { ...VALID_SESSION.cards[1], sequence_number: 0 }],
      }),
    );

    expectInvalidPracticeResponse(() =>
      parsePracticeSession({
        ...VALID_SESSION,
        cards: [
          { ...VALID_SESSION.cards[0], sequence_number: 3 },
          { ...VALID_SESSION.cards[1], sequence_number: 2 },
        ],
      }),
    );
  });
});

describe("parseSubmitPracticeAnswerResult", () => {
  it("maps feedback for an unfinished answer", () => {
    expect(parseSubmitPracticeAnswerResult(VALID_ANSWER_RESULT)).toEqual({
      isCorrect: false,
      answerText: "спасибо",
      answeredCount: 2,
      correctCount: 1,
      totalCount: 3,
      isFinished: false,
      timeToCompleteSeconds: null,
    });
  });

  it("accepts a finished result only with a non-negative completion time", () => {
    expect(
      parseSubmitPracticeAnswerResult({
        ...VALID_ANSWER_RESULT,
        answered_count: 3,
        correct_count: 2,
        is_finished: true,
        time_to_complete: 42,
      }),
    ).toMatchObject({ isFinished: true, timeToCompleteSeconds: 42 });
  });

  it.each([
    ["wrong field type", { is_correct: "false" }],
    ["zero answered count", { answered_count: 0, correct_count: 0 }],
    ["correct count above answered", { correct_count: 3 }],
    ["incorrect answer with no wrong count", { correct_count: 2 }],
    ["unfinished full counter", { answered_count: 3, correct_count: 2 }],
    ["finished partial counter", { is_finished: true, time_to_complete: 4 }],
    ["finished without time", { answered_count: 3, correct_count: 2, is_finished: true }],
    ["unfinished with time", { time_to_complete: 4 }],
    [
      "negative completion time",
      { answered_count: 3, correct_count: 2, is_finished: true, time_to_complete: -1 },
    ],
  ])("rejects %s", (_caseName, override) => {
    expectInvalidPracticeResponse(() =>
      parseSubmitPracticeAnswerResult({ ...VALID_ANSWER_RESULT, ...override }),
    );
  });

  it("requires a correct result to be represented in the aggregate counter", () => {
    expectInvalidPracticeResponse(() =>
      parseSubmitPracticeAnswerResult({
        ...VALID_ANSWER_RESULT,
        is_correct: true,
        answered_count: 1,
        correct_count: 0,
      }),
    );
  });
});
