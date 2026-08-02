import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../../api";
import { resumePracticeSession, startPracticeSession, submitPracticeAnswer } from "./practice-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const SESSION_UUID = "019c05e5-bc86-70e6-8f5c-d31bfa1aac10";
const OTHER_UUID = "f9b7ced5-fbea-4741-82fd-33ea144dab7c";

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

describe("startPracticeSession", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockResolvedValue(SESSION_RESPONSE);
  });

  it("posts the selected prompt side to the exact BFF start path", async () => {
    const controller = new AbortController();

    await expect(
      startPracticeSession(DECK_UUID, { promptSide: "front" }, controller.signal),
    ).resolves.toMatchObject({
      uuid: SESSION_UUID,
      deckUuid: DECK_UUID,
      promptSide: "front",
    });

    expect(apiFetch).toHaveBeenCalledOnce();
    expect(apiFetch).toHaveBeenCalledWith(`/bff/practice/${DECK_UUID}/start`, {
      method: "POST",
      body: { prompt_side: "front" },
      signal: controller.signal,
    });
  });

  it("rejects a session returned for a different deck", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ ...SESSION_RESPONSE, deck_uuid: OTHER_UUID });

    await expect(startPracticeSession(DECK_UUID, { promptSide: "front" })).rejects.toMatchObject({
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

    await expect(startPracticeSession(DECK_UUID, { promptSide: "front" })).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });

    vi.mocked(apiFetch).mockResolvedValueOnce({
      ...SESSION_RESPONSE,
      answered_count: 1,
      correct_count: 1,
      cards: [SESSION_RESPONSE.cards[1]],
    });

    await expect(startPracticeSession(DECK_UUID, { promptSide: "front" })).rejects.toMatchObject({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
    });
  });

  it("correlates canonical UUID values without case sensitivity", async () => {
    await expect(
      startPracticeSession(DECK_UUID.toUpperCase(), { promptSide: "front" }),
    ).resolves.toMatchObject({ deckUuid: DECK_UUID });
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
