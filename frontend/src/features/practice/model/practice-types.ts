export type CardSide = "front" | "back";
export type PracticeHistoryFilter = "all" | "completed" | "in_progress" | "abandoned";
export type TrainingSessionStatus = Exclude<PracticeHistoryFilter, "all">;
/** deck — тренировка по колоде, review — повторение слов из разных колод, без колоды. */
export type TrainingSessionKind = "deck" | "review";

export interface PracticeCard {
  sequenceNumber: number;
  promptText: string;
  promptLanguage: string;
  answerLanguage: string;
}

export interface PracticeSession {
  uuid: string;
  deckUuid: string | null;
  promptSide: CardSide;
  answerSide: CardSide;
  totalCount: number;
  answeredCount: number;
  correctCount: number;
  wrongCount: number;
  startedAt: string;
  cards: readonly PracticeCard[];
}

export interface PracticeHistorySession {
  uuid: string;
  kind: TrainingSessionKind;
  deckUuid: string | null;
  deckTitle: string | null;
  status: TrainingSessionStatus;
  requestedCount: number;
  answeredCount: number;
  correctCount: number;
  wrongCount: number;
  promptSide: CardSide;
  answerSide: CardSide;
  startedAt: string;
  finishedAt: string | null;
}

export interface PracticeHistoryPage {
  sessions: readonly PracticeHistorySession[];
  nextCursor: string | null;
  hasMore: boolean;
}

export interface PracticeSessionHistoryItem {
  itemUuid: string;
  sequenceNumber: number;
  promptText: string;
  answerText: string;
  promptLanguage: string;
  answerLanguage: string;
  userTypedText: string | null;
  isAnswered: boolean;
  isCorrect: boolean | null;
}

export interface PracticeDeckSummary {
  uuid: string;
  wordsCount: number;
}

export interface StartPracticeSessionInput {
  promptSide: CardSide;
  wordsPerSession: number;
}

export type PracticeActivityInput =
  | {
      event: "resume";
    }
  | {
      event: "heartbeat" | "pause";
      trackerUuid: string;
    };

export interface PracticeActivityResponse {
  trackerUuid: string | null;
}

export type SubmitPracticeAnswerInput =
  | {
      action: "answer";
      answer: string;
    }
  | {
      action: "skip";
    };

// Self-rating of an answer, the FSRS scale: 1 = again, 2 = hard, 3 = good, 4 = easy.
export type PracticeSelfRating = 1 | 2 | 3 | 4;

export const PRACTICE_SELF_RATINGS: readonly PracticeSelfRating[] = [1, 2, 3, 4];

export interface RatePracticeAnswerResult {
  rating: PracticeSelfRating;
  nextReviewAt: string | null;
}

export interface SubmitPracticeAnswerResult {
  isCorrect: boolean;
  answerText: string;
  answeredCount: number;
  correctCount: number;
  totalCount: number;
  isFinished: boolean;
  timeToCompleteSeconds: number | null;
  /** When the word comes back by the automatic rating of this answer; null without a schedule. */
  nextReviewAt: string | null;
}
