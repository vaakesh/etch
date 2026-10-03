import { describe, expect, it } from "vitest";
import { isApiError } from "../../../api";
import {
  parsePracticeDeckSummary,
  parsePracticeHistoryPage,
  parsePracticeSession,
  parsePracticeSessionHistory,
  parseSubmitPracticeAnswerResult,
} from "./practice-contract";
import { MAX_SESSION_SIZE } from "./practice-session-size";

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

const VALID_HISTORY_SESSION = {
  uuid: SESSION_UUID,
  deck_uuid: DECK_UUID,
  deck_title: "French basics",
  status: "completed",
  requested_count: 3,
  answered_count: 3,
  correct_count: 2,
  wrong_count: 1,
  prompt_side: "front",
  answer_side: "back",
  started_at: "2026-08-01T10:15:30Z",
  finished_at: "2026-08-01T10:18:30Z",
};

const VALID_SESSION_HISTORY_ITEM = {
  item_uuid: "f9b7ced5-fbea-4741-82fd-33ea144dab7c",
  sequence_number: 2,
  prompt_text: "bonjour",
  answer_text: "привет",
  prompt_lang: "fr",
  answer_lang: "ru",
  user_typed_text: "привет",
  is_answered: true,
  is_correct: true,
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
  it("resumes snapshots after deck deletion", () => {
    const session = parsePracticeSession({ ...VALID_SESSION, deck_uuid: null });

    expect(session.deckUuid).toBeNull();
    expect(session.cards).toHaveLength(2);
    expect(session.cards[0]?.promptText).toBe("merci");
  });
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
    [
      "total above the session limit",
      { total_count: MAX_SESSION_SIZE + 1, answered_count: 0, correct_count: 0, wrong_count: 0 },
    ],
  ])("rejects the %s invariant", (_caseName, override) => {
    expectInvalidPracticeResponse(() => parsePracticeSession({ ...VALID_SESSION, ...override }));
  });

  it("preserves sparse unanswered sequence numbers within the session size", () => {
    expect(
      parsePracticeSession({
        ...VALID_SESSION,
        total_count: 5,
        answered_count: 3,
        correct_count: 2,
        wrong_count: 1,
        cards: [VALID_SESSION.cards[0], { ...VALID_SESSION.cards[1], sequence_number: 5 }],
      }),
    ).toMatchObject({ cards: [{ sequenceNumber: 2 }, { sequenceNumber: 5 }] });
  });

  it("rejects duplicate, out-of-range, and unsorted card sequence numbers", () => {
    expectInvalidPracticeResponse(() =>
      parsePracticeSession({
        ...VALID_SESSION,
        cards: [
          VALID_SESSION.cards[0],
          { ...VALID_SESSION.cards[1], sequence_number: VALID_SESSION.total_count + 1 },
        ],
      }),
    );

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

describe("parsePracticeDeckSummary", () => {
  it("reads the canonical UUID and card count from a deck detail response", () => {
    expect(
      parsePracticeDeckSummary({ uuid: DECK_UUID, title: "French", words_count: 120 }),
    ).toEqual({ uuid: DECK_UUID, wordsCount: 120 });
  });

  it.each([
    null,
    {},
    { uuid: "not-a-uuid", words_count: 10 },
    { uuid: DECK_UUID, words_count: -1 },
  ])("rejects an invalid deck response", (payload) => {
    expectInvalidPracticeResponse(() => parsePracticeDeckSummary(payload));
  });
});

describe("parsePracticeHistoryPage", () => {
  it("keeps history and counters when the deck is deleted", () => {
    const page = parsePracticeHistoryPage({
      items: [{ ...VALID_HISTORY_SESSION, deck_uuid: null }],
      next_cursor: null,
      has_more: false,
    });

    expect(page.sessions[0]).toMatchObject({
      deckUuid: null,
      deckTitle: VALID_HISTORY_SESSION.deck_title,
      answeredCount: 3,
      correctCount: 2,
      wrongCount: 1,
    });
  });
  it("maps the training-session cursor page", () => {
    expect(
      parsePracticeHistoryPage({
        items: [VALID_HISTORY_SESSION],
        next_cursor: null,
        has_more: false,
      }),
    ).toEqual({
      sessions: [
        {
          uuid: SESSION_UUID,
          deckUuid: DECK_UUID,
          deckTitle: "French basics",
          status: "completed",
          requestedCount: 3,
          answeredCount: 3,
          correctCount: 2,
          wrongCount: 1,
          promptSide: "front",
          answerSide: "back",
          startedAt: "2026-08-01T10:15:30Z",
          finishedAt: "2026-08-01T10:18:30Z",
        },
      ],
      nextCursor: null,
      hasMore: false,
    });
  });

  it("preserves valid session statuses and rejects inconsistent completion states", () => {
    expect(
      parsePracticeHistoryPage({
        items: [{ ...VALID_HISTORY_SESSION, status: "in_progress", finished_at: null }],
        next_cursor: null,
        has_more: false,
      }).sessions[0],
    ).toMatchObject({ status: "in_progress", finishedAt: null });

    expect(
      parsePracticeHistoryPage({
        items: [
          {
            ...VALID_HISTORY_SESSION,
            status: "abandoned",
            answered_count: 1,
            correct_count: 1,
            wrong_count: 0,
          },
        ],
        next_cursor: null,
        has_more: false,
      }).sessions[0],
    ).toMatchObject({ status: "abandoned", answeredCount: 1 });

    for (const override of [
      { status: "in_progress" },
      { status: "completed", finished_at: null },
      { status: "abandoned", finished_at: null },
      { answered_count: 2, correct_count: 1, wrong_count: 1 },
      { finished_at: "2026-08-01T10:15:29Z" },
    ]) {
      expectInvalidPracticeResponse(() =>
        parsePracticeHistoryPage({
          items: [{ ...VALID_HISTORY_SESSION, ...override }],
          next_cursor: null,
          has_more: false,
        }),
      );
    }
  });

  it.each([
    ["unknown status", { items: [{ ...VALID_HISTORY_SESSION, status: "finished" }] }],
    ["invalid deck title", { items: [{ ...VALID_HISTORY_SESSION, deck_title: 42 }] }],
    ["invalid counters", { items: [{ ...VALID_HISTORY_SESSION, correct_count: 3 }] }],
    [
      "requested count above the session limit",
      { items: [{ ...VALID_HISTORY_SESSION, requested_count: MAX_SESSION_SIZE + 1 }] },
    ],
    ["same card side", { items: [{ ...VALID_HISTORY_SESSION, answer_side: "front" }] }],
    ["missing cursor", { has_more: true }],
  ])("rejects %s", (_caseName, override) => {
    expectInvalidPracticeResponse(() =>
      parsePracticeHistoryPage({
        items: [VALID_HISTORY_SESSION],
        next_cursor: null,
        has_more: false,
        ...override,
      }),
    );
  });
});

describe("parsePracticeSessionHistory", () => {
  it("maps the session item snapshot contract", () => {
    expect(parsePracticeSessionHistory([VALID_SESSION_HISTORY_ITEM])).toEqual([
      {
        itemUuid: VALID_SESSION_HISTORY_ITEM.item_uuid,
        sequenceNumber: 2,
        promptText: "bonjour",
        answerText: "привет",
        promptLanguage: "fr",
        answerLanguage: "ru",
        userTypedText: "привет",
        isAnswered: true,
        isCorrect: true,
      },
    ]);
  });

  it("accepts a not-yet-answered item only with a null result", () => {
    expect(
      parsePracticeSessionHistory([
        {
          ...VALID_SESSION_HISTORY_ITEM,
          user_typed_text: null,
          is_answered: false,
          is_correct: null,
        },
      ]),
    ).toMatchObject([{ userTypedText: null, isAnswered: false, isCorrect: null }]);

    expectInvalidPracticeResponse(() =>
      parsePracticeSessionHistory([
        {
          ...VALID_SESSION_HISTORY_ITEM,
          user_typed_text: null,
          is_answered: false,
          is_correct: false,
        },
      ]),
    );
  });

  it("distinguishes a skipped item from a typed answer", () => {
    expect(
      parsePracticeSessionHistory([
        {
          ...VALID_SESSION_HISTORY_ITEM,
          user_typed_text: null,
          is_correct: false,
        },
      ]),
    ).toMatchObject([{ userTypedText: null, isAnswered: true, isCorrect: false }]);

    expectInvalidPracticeResponse(() =>
      parsePracticeSessionHistory([
        {
          ...VALID_SESSION_HISTORY_ITEM,
          user_typed_text: null,
          is_correct: true,
        },
      ]),
    );
  });

  it("rejects malformed lists and duplicate sequence numbers", () => {
    expectInvalidPracticeResponse(() => parsePracticeSessionHistory({ items: [] }));
    expectInvalidPracticeResponse(() =>
      parsePracticeSessionHistory([
        { ...VALID_SESSION_HISTORY_ITEM, sequence_number: MAX_SESSION_SIZE + 1 },
      ]),
    );
    expectInvalidPracticeResponse(() =>
      parsePracticeSessionHistory([
        VALID_SESSION_HISTORY_ITEM,
        {
          ...VALID_SESSION_HISTORY_ITEM,
          item_uuid: "019c05e5-bc86-70e6-8f5c-d31bfa1aac11",
        },
      ]),
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
