import { useCallback, useEffect, useLayoutEffect, useReducer, useRef } from "react";
import {
  INITIAL_PRACTICE_RATING_FLOW,
  PRACTICE_RATING_ADVANCE_DELAY_MS,
  reducePracticeRatingFlow,
  shouldLeaveRatedCard,
  type PracticeRatingFlowState,
} from "../../features/practice/model/practice-rating-flow";
import type { PracticeSelfRating } from "../../features/practice/model/practice-types";
import type { PracticeRatingOutcome } from "../../features/practice/model/usePracticeSession";

export interface UsePracticeRatingFlowResult {
  state: PracticeRatingFlowState;
  select: (rating: PracticeSelfRating) => void;
  /** Enter: leaves the card without a rating, or skips the wait after a chosen one. */
  proceed: () => void;
}

/** The flow lives as long as one card view: the card view is remounted for every card. */
export function usePracticeRatingFlow(
  rate: (rating: PracticeSelfRating) => Promise<PracticeRatingOutcome>,
  leaveCard: () => void,
): UsePracticeRatingFlowResult {
  const [state, dispatch] = useReducer(reducePracticeRatingFlow, INITIAL_PRACTICE_RATING_FLOW);
  // Keys arrive faster than re-renders, so the guards read refs instead of state.
  const isConfirmingRef = useRef(false);
  const hasLeftRef = useRef(false);
  const isMountedRef = useRef(true);
  const leaveCardRef = useRef(leaveCard);
  const isConfirming = state.status === "confirming";

  useLayoutEffect(() => {
    leaveCardRef.current = leaveCard;
  });

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!isConfirming) {
      return;
    }

    const timer = window.setTimeout(
      () => dispatch({ type: "delayElapsed" }),
      PRACTICE_RATING_ADVANCE_DELAY_MS,
    );
    return () => window.clearTimeout(timer);
  }, [isConfirming]);

  useEffect(() => {
    if (shouldLeaveRatedCard(state) && !hasLeftRef.current) {
      hasLeftRef.current = true;
      leaveCardRef.current();
    }
  }, [state]);

  const select = useCallback(
    (rating: PracticeSelfRating) => {
      if (isConfirmingRef.current || hasLeftRef.current) {
        return;
      }

      isConfirmingRef.current = true;
      dispatch({ type: "select", rating });
      void rate(rating).then((outcome) => {
        if (!isMountedRef.current) {
          return;
        }
        if (outcome.status === "saved") {
          dispatch({ type: "saved", nextReviewAt: outcome.nextReviewAt });
        } else if (outcome.status === "failed") {
          isConfirmingRef.current = false;
          dispatch({ type: "failed", error: outcome.error });
        }
      });
    },
    [rate],
  );

  const proceed = useCallback(() => {
    if (hasLeftRef.current) {
      return;
    }
    if (isConfirmingRef.current) {
      dispatch({ type: "skip" });
      return;
    }

    hasLeftRef.current = true;
    leaveCardRef.current();
  }, []);

  return { state, select, proceed };
}
