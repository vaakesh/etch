import { useCallback, useEffect, useRef, useState } from "react";
import { isApiError } from "../../../api";
import { MAX_SESSION_SIZE } from "../../practice/model/practice-session-size";
import type { CardSide, PracticeSession } from "../../practice/model/practice-types";
import { getReviewSummary, startReviewSession } from "../api/review-api";
import type { ReviewSummary } from "./review-types";

export type ReviewSummaryState =
  | { status: "loading" }
  | { status: "success"; data: ReviewSummary }
  | { status: "error"; error: unknown };

export type ReviewStartState =
  | { status: "idle" }
  | { status: "starting"; side: CardSide }
  | { status: "error"; side: CardSide; error: unknown };

interface UseReviewTodayResult {
  summary: ReviewSummaryState;
  startState: ReviewStartState;
  retry: () => void;
  /** Стартует повторение всех слов на сегодня; `null` — старт не удался или уже идёт. */
  start: (side: CardSide) => Promise<PracticeSession | null>;
}

const LOADING_STATE: ReviewSummaryState = { status: "loading" };
const IDLE_START_STATE: ReviewStartState = { status: "idle" };

export function useReviewToday(): UseReviewTodayResult {
  const [summary, setSummary] = useState<ReviewSummaryState>(LOADING_STATE);
  const [startState, setStartState] = useState<ReviewStartState>(IDLE_START_STATE);
  const [revision, setRevision] = useState(0);
  const isStartingRef = useRef(false);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    void getReviewSummary(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setSummary({ status: "success", data });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setSummary({ status: "error", error });
        }
      });

    return () => controller.abort();
  }, [revision]);

  const retry = useCallback((): void => {
    setSummary(LOADING_STATE);
    setRevision((current) => current + 1);
  }, []);

  const start = useCallback(
    async (side: CardSide): Promise<PracticeSession | null> => {
      if (summary.status !== "success" || isStartingRef.current) {
        return null;
      }

      const dueToday = summary.data.sides[side].dueToday;
      if (dueToday < 1) {
        return null;
      }

      isStartingRef.current = true;
      setStartState({ status: "starting", side });
      try {
        const session = await startReviewSession({
          promptSide: side,
          wordsPerSession: Math.min(dueToday, MAX_SESSION_SIZE),
        });
        return session;
      } catch (error: unknown) {
        if (isMountedRef.current) {
          setStartState({ status: "error", side, error });
          // 409: слова уже повторены или сессию начали в другой вкладке —
          // сводка устарела, обновляем её без сброса в загрузку
          if (isApiError(error) && error.status === 409) {
            setRevision((current) => current + 1);
          }
        }
        return null;
      } finally {
        isStartingRef.current = false;
      }
    },
    [summary],
  );

  return { summary, startState, retry, start };
}
