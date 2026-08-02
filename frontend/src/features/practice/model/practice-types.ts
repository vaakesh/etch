export type CardSide = "front" | "back";

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
