export type CardSide = "front" | "back";
export type PracticeHistoryFilter = "all" | "completed" | "in_progress" | "abandoned";
export type TrainingSessionStatus = Exclude<PracticeHistoryFilter, "all">;

export interface PracticeCard {
  sequenceNumber: number;
  promptText: string;
  promptLanguage: string;
  answerLanguage: string;
}

export interface PracticeSession {
  uuid: string;
  deckUuid: string;
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
  deckUuid: string;
  status: TrainingSessionStatus;
  requestedCount: number;
  actualCount: number;
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

export interface StartPracticeSessionInput {
  promptSide: CardSide;
}

export type SubmitPracticeAnswerInput =
  | {
      action: "answer";
      answer: string;
    }
  | {
      action: "skip";
    };

export interface SubmitPracticeAnswerResult {
  isCorrect: boolean;
  answerText: string;
  answeredCount: number;
  correctCount: number;
  totalCount: number;
  isFinished: boolean;
  timeToCompleteSeconds: number | null;
}
