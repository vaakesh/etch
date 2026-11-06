import type { PracticeSelfRating } from "./practice-types";

/** How long the chosen rating stays on screen before the next card opens. */
export const PRACTICE_RATING_ADVANCE_DELAY_MS = 900;

/**
 * Self-rating after an answer: a digit picks the rating and sends it at once, the choice is shown
 * for PRACTICE_RATING_ADVANCE_DELAY_MS and then the next card opens. Enter skips the wait, but the
 * card is left only after the backend has saved the rating: a failed save returns to the choice.
 */
export type PracticeRatingFlowState =
  | { status: "choosing"; error: unknown }
  | {
      status: "confirming";
      rating: PracticeSelfRating;
      isSaved: boolean;
      // Next review of the word after the save; null until saved or when the backend has none.
      nextReviewAt: string | null;
      isDelayOver: boolean;
      isSkipRequested: boolean;
    };

export type PracticeRatingFlowEvent =
  | { type: "select"; rating: PracticeSelfRating }
  | { type: "saved"; nextReviewAt: string | null }
  | { type: "failed"; error: unknown }
  | { type: "delayElapsed" }
  | { type: "skip" };

export const INITIAL_PRACTICE_RATING_FLOW: PracticeRatingFlowState = {
  status: "choosing",
  error: null,
};

export function reducePracticeRatingFlow(
  state: PracticeRatingFlowState,
  event: PracticeRatingFlowEvent,
): PracticeRatingFlowState {
  if (state.status === "choosing") {
    return event.type === "select"
      ? {
          status: "confirming",
          rating: event.rating,
          isSaved: false,
          nextReviewAt: null,
          isDelayOver: false,
          isSkipRequested: false,
        }
      : state;
  }

  switch (event.type) {
    case "saved":
      return { ...state, isSaved: true, nextReviewAt: event.nextReviewAt };
    case "failed":
      return { status: "choosing", error: event.error };
    case "delayElapsed":
      return { ...state, isDelayOver: true };
    case "skip":
      return { ...state, isSkipRequested: true };
    case "select":
      return state;
  }
}

export function shouldLeaveRatedCard(state: PracticeRatingFlowState): boolean {
  return (
    state.status === "confirming" && state.isSaved && (state.isDelayOver || state.isSkipRequested)
  );
}
