import { describe, expect, it } from "vitest";
import { isApiError } from "../../../api";
import { parseReviewSummary } from "./review-contract";

const SESSION_UUID = "0198ad01-b200-7000-8000-000000000400";

function buildResponse(overrides: Record<string, unknown> = {}) {
  return {
    timezone: "Europe/Moscow",
    sides: {
      front: { due_now: 3, due_today: 5, next_due_at: "2026-11-06T18:30:00.123456Z" },
      back: { due_now: 0, due_today: 0, next_due_at: null },
    },
    active_session: {
      training_session_uuid: SESSION_UUID.toUpperCase(),
      prompt_side: "back",
      answered_count: 2,
      total_count: 10,
    },
    ...overrides,
  };
}

function expectInvalid(value: unknown, path: string): void {
  try {
    parseReviewSummary(value);
  } catch (error) {
    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error.code).toBe("INVALID_REVIEW_RESPONSE");
      expect(error.message).toContain(path);
    }
    return;
  }
  throw new Error("expected the review summary to be rejected");
}

describe("parseReviewSummary", () => {
  it("maps the backend summary to the review model", () => {
    expect(parseReviewSummary(buildResponse())).toEqual({
      timezone: "Europe/Moscow",
      sides: {
        front: { dueNow: 3, dueToday: 5, nextDueAt: "2026-11-06T18:30:00.123456Z" },
        back: { dueNow: 0, dueToday: 0, nextDueAt: null },
      },
      activeSession: {
        uuid: SESSION_UUID,
        promptSide: "back",
        answeredCount: 2,
        totalCount: 10,
      },
    });
  });

  it("accepts a summary without an active session", () => {
    expect(parseReviewSummary(buildResponse({ active_session: null })).activeSession).toBeNull();
  });

  it.each([
    [
      "due_now above due_today",
      {
        sides: {
          front: { due_now: 6, due_today: 5, next_due_at: null },
          back: { due_now: 0, due_today: 0, next_due_at: null },
        },
      },
      "sides.front.due_now",
    ],
    [
      "negative counter",
      {
        sides: {
          front: { due_now: 0, due_today: 0, next_due_at: null },
          back: { due_now: -1, due_today: 0, next_due_at: null },
        },
      },
      "sides.back.due_now",
    ],
    [
      "naive next_due_at",
      {
        sides: {
          front: { due_now: 0, due_today: 0, next_due_at: "2026-11-06T18:30:00" },
          back: { due_now: 0, due_today: 0, next_due_at: null },
        },
      },
      "sides.front.next_due_at",
    ],
    ["missing side", { sides: { front: { due_now: 0, due_today: 0, next_due_at: null } } }, "back"],
    ["empty timezone", { timezone: "" }, "timezone"],
    [
      "answered above total",
      {
        active_session: {
          training_session_uuid: SESSION_UUID,
          prompt_side: "front",
          answered_count: 11,
          total_count: 10,
        },
      },
      "active_session.answered_count",
    ],
    [
      "unknown prompt side",
      {
        active_session: {
          training_session_uuid: SESSION_UUID,
          prompt_side: "left",
          answered_count: 0,
          total_count: 10,
        },
      },
      "active_session.prompt_side",
    ],
  ])("rejects %s", (_, overrides, path) => {
    expectInvalid(buildResponse(overrides), path);
  });
});
