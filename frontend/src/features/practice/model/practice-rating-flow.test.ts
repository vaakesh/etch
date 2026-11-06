import { describe, expect, it } from "vitest";
import {
  INITIAL_PRACTICE_RATING_FLOW,
  reducePracticeRatingFlow,
  shouldLeaveRatedCard,
  type PracticeRatingFlowEvent,
  type PracticeRatingFlowState,
} from "./practice-rating-flow";

const SAVED = { type: "saved", nextReviewAt: null } as const;

function run(...events: PracticeRatingFlowEvent[]): PracticeRatingFlowState {
  return events.reduce(reducePracticeRatingFlow, INITIAL_PRACTICE_RATING_FLOW);
}

describe("practice rating flow", () => {
  it("stays on the card right after a digit is chosen", () => {
    const state = run({ type: "select", rating: 3 });

    expect(state).toEqual({
      status: "confirming",
      rating: 3,
      isSaved: false,
      nextReviewAt: null,
      isDelayOver: false,
      isSkipRequested: false,
    });
    expect(shouldLeaveRatedCard(state)).toBe(false);
  });

  it("keeps the next review time from the save while the rating stays on screen", () => {
    const state = run(
      { type: "select", rating: 3 },
      { type: "saved", nextReviewAt: "2026-11-10T09:00:00Z" },
    );

    expect(state).toEqual({
      status: "confirming",
      rating: 3,
      isSaved: true,
      nextReviewAt: "2026-11-10T09:00:00Z",
      isDelayOver: false,
      isSkipRequested: false,
    });
    expect(shouldLeaveRatedCard(state)).toBe(false);
  });

  it.each([
    ["saved, then the animation ends", [SAVED, { type: "delayElapsed" }]],
    ["the animation ends, then saved", [{ type: "delayElapsed" }, SAVED]],
    ["Enter skips the animation after the save", [SAVED, { type: "skip" }]],
    ["Enter skips the animation before the save", [{ type: "skip" }, SAVED]],
  ] as const)("leaves the card when %s", (_, events) => {
    const state = run({ type: "select", rating: 2 }, ...events);

    expect(shouldLeaveRatedCard(state)).toBe(true);
  });

  it.each([
    ["the animation ended", { type: "delayElapsed" }],
    ["Enter was pressed", { type: "skip" }],
  ] as const)("waits for the backend even when %s", (_, event) => {
    expect(shouldLeaveRatedCard(run({ type: "select", rating: 4 }, event))).toBe(false);
  });

  it("returns to the choice with the error when the save fails", () => {
    const error = new Error("offline");
    const state = run({ type: "select", rating: 1 }, { type: "skip" }, { type: "failed", error });

    expect(state).toEqual({ status: "choosing", error });
    expect(shouldLeaveRatedCard(reducePracticeRatingFlow(state, { type: "delayElapsed" }))).toBe(
      false,
    );
  });

  it("allows a new digit after a failed save and clears the error", () => {
    const state = run(
      { type: "select", rating: 1 },
      { type: "failed", error: new Error("offline") },
      { type: "select", rating: 2 },
    );

    expect(state).toMatchObject({ status: "confirming", rating: 2 });
  });

  it("ignores a second digit while the first rating is confirmed", () => {
    const state = run({ type: "select", rating: 3 }, { type: "select", rating: 1 });

    expect(state).toMatchObject({ status: "confirming", rating: 3 });
  });

  it.each([SAVED, { type: "delayElapsed" }, { type: "skip" }] as const)(
    "ignores $type before any rating is chosen",
    (event) => {
      expect(run(event)).toBe(INITIAL_PRACTICE_RATING_FLOW);
    },
  );
});
