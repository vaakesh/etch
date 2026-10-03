import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../../api";
import {
  getPracticeSessionItemsHistory,
  getPracticeSessionHistory,
  recordPracticeActivity,
  resumePracticeSession,
  startPracticeSession,
  submitPracticeAnswer,
  validatePracticeDeck,
} from "./practice-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const SESSION_UUID = "019c05e5-bc86-70e6-8f5c-d31bfa1aac10";
const OTHER_UUID = "f9b7ced5-fbea-4741-82fd-33ea144dab7c";
const TRACKER_UUID = "019c05e5-bc86-70e6-8f5c-d31bfa1aac11";
const START_INPUT = { promptSide: "front", wordsPerSession: 50 } as const;

const SESSION_RESPONSE = {
  training_session_uuid: SESSION_UUID,
  deck_uuid: DECK_UUID,
  prompt_side: "front",
  answer_side: "back",
  total_count: 2,
  answered_count: 0,
  correct_count: 0,
  wrong_count: 0,
  started_at: "2026-08-01T10:15:30Z",
  cards: [
    {
      sequence_number: 1,
      prompt_text: "bonjour",
      prompt_language: "fr",
      answer_language: "ru",
    },
    {
      sequence_number: 2,
      prompt_text: "merci",
      prompt_language: "fr",
      answer_language: "ru",
    },
  ],
};

const ANSWER_RESPONSE = {
  is_correct: true,
  answer_text: "привет",
  answered_count: 1,
  correct_count: 1,
  total_count: 2,
  is_finished: false,
  time_to_complete: null,
};

const HISTORY_SESSION_RESPONSE = {
  uuid: SESSION_UUID,
  deck_uuid: DECK_UUID,
  deck_title: "French basics",
  status: "completed",
  requested_count: 2,
  answered_count: 2,
  correct_count: 1,
  wrong_count: 1,
  prompt_side: "front",
  answer_side: "back",
  started_at: "2026-08-01T10:15:30Z",
  finished_at: "2026-08-01T10:16:30Z",
};

const SESSION_HISTORY_ITEM_RESPONSE = {
  item_uuid: OTHER_UUID,
  sequence_number: 2,
  prompt_text: "bonjour",
  answer_text: "привет",
  prompt_lang: "fr",
  answer_lang: "ru",
  user_typed_text: "привет",
  is_answered: true,
  is_correct: true,
};

describe("getPracticeSessionHistory", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("loads every cursor page from the exact current-user sessions path", async () => {
    vi.mocked(apiFetch)
      .mockResolvedValueOnce({
        items: [HISTORY_SESSION_RESPONSE],
        next_cursor: "next-page",
        has_more: true,
      })
      .mockResolvedValueOnce({
        items: [
          {
            ...HISTORY_SESSION_RESPONSE,
            uuid: OTHER_UUID,
            status: "in_progress",
            answered_count: 0,
            correct_count: 0,
            wrong_count: 0,
            finished_at: null,
          },
        ],
        next_cursor: null,
        has_more: false,
      });

    await expect(getPracticeSessionHistory("all")).resolves.toMatchObject([
      { uuid: SESSION_UUID, status: "completed" },
      { uuid: OTHER_UUID, status: "in_progress" },
    ]);

    expect(apiFetch).toHaveBeenNthCalledWith(1, "/users/me/training-sessions", {
      query: { cursor: null, limit: 100, status: null },
      signal: undefined,
    });
    expect(apiFetch).toHaveBeenNthCalledWith(2, "/users/me/training-sessions", {
      query: { cursor: "next-page", limit: 100, status: null },
      signal: undefined,
    });
  });

  it("rejects a repeated backend cursor", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      items: [],
      next_cursor: "same-page",
      has_more: true,
    });

    await expect(getPracticeSessionHistory("all")).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });
  });

  it.each(["completed", "in_progress", "abandoned"] as const)(
    "requests the %s filter from the backend",
    async (status) => {
      vi.mocked(apiFetch).mockResolvedValue({
        items: [
          {
            ...HISTORY_SESSION_RESPONSE,
            status,
            finished_at: status === "in_progress" ? null : HISTORY_SESSION_RESPONSE.finished_at,
          },
        ],
        next_cursor: null,
        has_more: false,
      });

      await expect(getPracticeSessionHistory(status)).resolves.toMatchObject([{ status }]);
      expect(apiFetch).toHaveBeenCalledWith("/users/me/training-sessions", {
        query: { cursor: null, limit: 100, status },
        signal: undefined,
      });
    },
  );

  it("rejects a session outside the backend filter", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      items: [HISTORY_SESSION_RESPONSE],
      next_cursor: null,
      has_more: false,
    });

    await expect(getPracticeSessionHistory("in_progress")).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });
  });
});

describe("getPracticeSessionItemsHistory", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("loads and maps the exact session history endpoint", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValue([SESSION_HISTORY_ITEM_RESPONSE]);

    await expect(getPracticeSessionItemsHistory(SESSION_UUID, controller.signal)).resolves.toEqual([
      {
        itemUuid: OTHER_UUID,
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

    expect(apiFetch).toHaveBeenCalledWith(`/training-sessions/${SESSION_UUID}/history`, {
      query: { ps: 100, pn: 1 },
      signal: controller.signal,
    });
  });

  it("loads every numbered page and sorts the resulting snapshots", async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => ({
      ...SESSION_HISTORY_ITEM_RESPONSE,
      item_uuid: `019c05e5-bc86-70e6-8f5c-${String(index + 1).padStart(12, "0")}`,
      sequence_number: 100 - index,
    }));
    vi.mocked(apiFetch)
      .mockResolvedValueOnce(firstPage)
      .mockResolvedValueOnce([
        {
          ...SESSION_HISTORY_ITEM_RESPONSE,
          item_uuid: "019c05e5-bc86-70e6-8f5c-d31bfa1aac11",
          sequence_number: 101,
        },
      ]);

    const items = await getPracticeSessionItemsHistory(SESSION_UUID);

    expect(items).toHaveLength(101);
    expect(items[0]?.sequenceNumber).toBe(1);
    expect(items[100]?.sequenceNumber).toBe(101);
    expect(apiFetch).toHaveBeenNthCalledWith(2, `/training-sessions/${SESSION_UUID}/history`, {
      query: { ps: 100, pn: 2 },
      signal: undefined,
    });
  });
});

describe("validatePracticeDeck", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue({ uuid: DECK_UUID, words_count: 120 });
  });

  it("checks the exact backend deck path before rendering practice setup", async () => {
    const controller = new AbortController();

    await expect(validatePracticeDeck(DECK_UUID, controller.signal)).resolves.toEqual({
      uuid: DECK_UUID,
      wordsCount: 120,
    });
    expect(apiFetch).toHaveBeenCalledWith(`/decks/${DECK_UUID}`, {
      signal: controller.signal,
    });
  });

  it("rejects a response for a different deck", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ uuid: OTHER_UUID, words_count: 120 });

    await expect(validatePracticeDeck(DECK_UUID)).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });
  });
});

describe("startPracticeSession", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(SESSION_RESPONSE);
  });

  it("posts the selected prompt side and word count to the exact BFF start path", async () => {
    const controller = new AbortController();

    await expect(
      startPracticeSession(DECK_UUID, START_INPUT, controller.signal),
    ).resolves.toMatchObject({
      uuid: SESSION_UUID,
      deckUuid: DECK_UUID,
      promptSide: "front",
    });

    expect(apiFetch).toHaveBeenCalledOnce();
    expect(apiFetch).toHaveBeenCalledWith(`/bff/practice/${DECK_UUID}/start`, {
      method: "POST",
      body: { prompt_side: "front", words_per_session: 50 },
      signal: controller.signal,
    });
  });

  it("rejects a session returned for a different deck", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ...SESSION_RESPONSE, deck_uuid: OTHER_UUID });

    await expect(startPracticeSession(DECK_UUID, START_INPUT)).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });
  });

  it("rejects start counters or a prompt side that do not match the request", async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({
      ...SESSION_RESPONSE,
      prompt_side: "back",
      answer_side: "front",
    });

    await expect(startPracticeSession(DECK_UUID, START_INPUT)).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });

    vi.mocked(apiFetch).mockResolvedValueOnce({
      ...SESSION_RESPONSE,
      answered_count: 1,
      correct_count: 1,
      cards: [SESSION_RESPONSE.cards[1]],
    });

    await expect(startPracticeSession(DECK_UUID, START_INPUT)).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });
  });

  it("rejects a session containing more cards than requested", async () => {
    await expect(
      startPracticeSession(DECK_UUID, { promptSide: "front", wordsPerSession: 1 }),
    ).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });
  });

  it("correlates canonical UUID values without case sensitivity", async () => {
    await expect(startPracticeSession(DECK_UUID.toUpperCase(), START_INPUT)).resolves.toMatchObject(
      { deckUuid: DECK_UUID },
    );
  });
});

describe("resumePracticeSession", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(SESSION_RESPONSE);
  });

  it("gets the exact BFF resume path without a trailing slash", async () => {
    const controller = new AbortController();

    await expect(resumePracticeSession(SESSION_UUID, controller.signal)).resolves.toMatchObject({
      uuid: SESSION_UUID,
      cards: [{ sequenceNumber: 1 }, { sequenceNumber: 2 }],
    });

    expect(apiFetch).toHaveBeenCalledOnce();
    expect(apiFetch).toHaveBeenCalledWith(`/bff/practice/${SESSION_UUID}/resume`, {
      signal: controller.signal,
    });
  });

  it("rejects a response for a different session UUID", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ...SESSION_RESPONSE,
      training_session_uuid: OTHER_UUID,
    });

    await expect(resumePracticeSession(SESSION_UUID)).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });
  });

  it("rejects a completed payload from the unfinished-session resume endpoint", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ...SESSION_RESPONSE,
      answered_count: 2,
      correct_count: 1,
      wrong_count: 1,
      cards: [],
    });

    await expect(resumePracticeSession(SESSION_UUID)).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });
  });

  it("correlates an uppercase session query with the canonical response UUID", async () => {
    await expect(resumePracticeSession(SESSION_UUID.toUpperCase())).resolves.toMatchObject({
      uuid: SESSION_UUID,
    });
  });
});

describe("submitPracticeAnswer", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(ANSWER_RESPONSE);
  });

  it("puts an answer on the exact session item path", async () => {
    const controller = new AbortController();

    await expect(
      submitPracticeAnswer(
        SESSION_UUID,
        2,
        { action: "answer", answer: "привет" },
        controller.signal,
      ),
    ).resolves.toEqual({
      isCorrect: true,
      answerText: "привет",
      answeredCount: 1,
      correctCount: 1,
      totalCount: 2,
      isFinished: false,
      timeToCompleteSeconds: null,
    });

    expect(apiFetch).toHaveBeenCalledOnce();
    expect(apiFetch).toHaveBeenCalledWith(`/training-sessions/${SESSION_UUID}/items/2/submit`, {
      method: "PUT",
      body: { action: "answer", answer: "привет" },
      signal: controller.signal,
    });
  });

  it("sends the skip discriminator without inventing an answer", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      ...ANSWER_RESPONSE,
      is_correct: false,
      correct_count: 0,
    });

    await expect(submitPracticeAnswer(SESSION_UUID, 1, { action: "skip" })).resolves.toMatchObject({
      isCorrect: false,
      answerText: "привет",
    });

    expect(apiFetch).toHaveBeenCalledWith(`/training-sessions/${SESSION_UUID}/items/1/submit`, {
      method: "PUT",
      body: { action: "skip" },
      signal: undefined,
    });
  });
});

describe("recordPracticeActivity", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue({ tracker_uuid: TRACKER_UUID });
  });

  it("posts resume without a client-generated tracker", async () => {
    await expect(recordPracticeActivity(SESSION_UUID, { event: "resume" })).resolves.toEqual({
      trackerUuid: TRACKER_UUID,
    });

    expect(apiFetch).toHaveBeenCalledWith(`/training-sessions/${SESSION_UUID}/activity`, {
      method: "POST",
      body: { event: "resume" },
      keepalive: undefined,
    });
  });

  it.each(["heartbeat", "pause"] as const)(
    "posts %s with the backend tracker and keepalive option",
    async (event) => {
      await recordPracticeActivity(
        SESSION_UUID,
        { event, trackerUuid: TRACKER_UUID },
        { keepalive: true },
      );

      expect(apiFetch).toHaveBeenCalledWith(`/training-sessions/${SESSION_UUID}/activity`, {
        method: "POST",
        body: { event, tracker_uuid: TRACKER_UUID },
        keepalive: true,
      });
    },
  );

  it("accepts null when the backend no longer tracks the session", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ tracker_uuid: null });

    await expect(recordPracticeActivity(SESSION_UUID, { event: "resume" })).resolves.toEqual({
      trackerUuid: null,
    });
  });

  it("rejects an invalid activity response", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ tracker_uuid: "not-a-uuid" });

    await expect(recordPracticeActivity(SESSION_UUID, { event: "resume" })).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });
  });
});
