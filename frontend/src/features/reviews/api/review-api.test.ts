import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, isApiError } from "../../../api";
import { getReviewSummary, startReviewSession } from "./review-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const SESSION_UUID = "0198ad01-b200-7000-8000-000000000400";

const SUMMARY = {
  timezone: "UTC",
  sides: {
    front: { due_now: 1, due_today: 2, next_due_at: null },
    back: { due_now: 0, due_today: 0, next_due_at: null },
  },
  active_session: null,
};

function buildStartedSession(overrides: Record<string, unknown> = {}) {
  return {
    training_session_uuid: SESSION_UUID,
    kind: "review",
    deck_uuid: null,
    prompt_side: "front",
    answer_side: "back",
    total_count: 2,
    answered_count: 0,
    correct_count: 0,
    wrong_count: 0,
    started_at: "2026-11-06T12:00:00Z",
    cards: [
      { sequence_number: 1, prompt_text: "кот", prompt_language: "ru", answer_language: "en" },
      { sequence_number: 2, prompt_text: "пёс", prompt_language: "ru", answer_language: "en" },
    ],
    ...overrides,
  };
}

describe("review API", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("loads the summary from the exact BFF route with the caller signal", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValue(SUMMARY);

    await expect(getReviewSummary(controller.signal)).resolves.toMatchObject({ timezone: "UTC" });

    expect(apiFetch).toHaveBeenCalledOnce();
    expect(apiFetch).toHaveBeenCalledWith("/bff/reviews/summary", { signal: controller.signal });
  });

  it("starts a review session with the backend request body", async () => {
    vi.mocked(apiFetch).mockResolvedValue(buildStartedSession());

    const session = await startReviewSession({ promptSide: "front", wordsPerSession: 2 });

    expect(session).toMatchObject({ uuid: SESSION_UUID, deckUuid: null, totalCount: 2 });
    expect(apiFetch).toHaveBeenCalledWith("/bff/reviews/start", {
      method: "POST",
      body: { prompt_side: "front", words_per_session: 2 },
      signal: undefined,
    });
  });

  it.each([
    ["a deck session", { deck_uuid: "0198ad01-b200-7000-8000-000000000200" }, 2],
    ["another prompt side", { prompt_side: "back", answer_side: "front" }, 2],
    ["more words than requested", {}, 1],
  ])("rejects %s as the started review", async (_, overrides, wordsPerSession) => {
    vi.mocked(apiFetch).mockResolvedValue(buildStartedSession(overrides));

    const result = startReviewSession({ promptSide: "front", wordsPerSession });

    await expect(result).rejects.toSatisfy(
      (error: unknown) => isApiError(error) && error.code === "INVALID_REVIEW_RESPONSE",
    );
  });
});
