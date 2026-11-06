import type { CardSide } from "../../practice/model/practice-types";

export interface ReviewSideSummary {
  /** Слова, срок повторения которых уже наступил. */
  dueNow: number;
  /** Слова со сроком до конца дня пользователя, включая `dueNow`. */
  dueToday: number;
  /** Ближайший срок после текущего момента; `null` — повторять больше нечего. */
  nextDueAt: string | null;
}

export interface ActiveReviewSession {
  uuid: string;
  promptSide: CardSide;
  answeredCount: number;
  totalCount: number;
}

export interface ReviewSummary {
  timezone: string;
  /** Ключ — `prompt_side`, с которой стартует сессия повторения. */
  sides: Readonly<Record<CardSide, ReviewSideSummary>>;
  activeSession: ActiveReviewSession | null;
}
