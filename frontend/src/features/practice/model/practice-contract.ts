import { ApiError } from "../../../api";
import type {
  CardSide,
  PracticeActivityResponse,
  PracticeCard,
  PracticeDeckSummary,
  PracticeHistoryPage,
  PracticeHistorySession,
  PracticeSession,
  PracticeSessionHistoryItem,
  SubmitPracticeAnswerResult,
  TrainingSessionStatus,
} from "./practice-types";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DATE_TIME_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-](\d{2}):(\d{2}))$/;

function invalidPracticeResponse(path: string): never {
  throw new ApiError({
    status: 0,
    code: "INVALID_PRACTICE_RESPONSE",
    message: `The backend returned an unexpected practice value at ${path}.`,
  });
}

function readRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return invalidPracticeResponse(path);
  }

  return value as Record<string, unknown>;
}

function readString(value: unknown, path: string): string {
  if (typeof value !== "string") {
    return invalidPracticeResponse(path);
  }

  return value;
}

function readBoolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") {
    return invalidPracticeResponse(path);
  }

  return value;
}

function readNullableBoolean(value: unknown, path: string): boolean | null {
  if (value === null) {
    return null;
  }

  return readBoolean(value, path);
}

function readInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value)) {
    return invalidPracticeResponse(path);
  }

  return value;
}

function readNullableInteger(value: unknown, path: string): number | null {
  if (value === null) {
    return null;
  }

  return readInteger(value, path);
}

function readNullableString(value: unknown, path: string): string | null {
  if (value === null) {
    return null;
  }

  return readString(value, path);
}

function readUuid(value: unknown, path: string): string {
  const uuid = readString(value, path);

  if (!UUID_PATTERN.test(uuid)) {
    return invalidPracticeResponse(path);
  }

  return uuid;
}

function readNullableUuid(value: unknown, path: string): string | null {
  if (value === null) {
    return null;
  }

  return readUuid(value, path);
}

function readCardSide(value: unknown, path: string): CardSide {
  if (value !== "front" && value !== "back") {
    return invalidPracticeResponse(path);
  }

  return value;
}

function readTrainingSessionStatus(value: unknown, path: string): TrainingSessionStatus {
  if (value !== "completed" && value !== "in_progress" && value !== "abandoned") {
    return invalidPracticeResponse(path);
  }

  return value;
}

function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

function getDaysInMonth(year: number, month: number): number {
  const monthLengths = [31, isLeapYear(year) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return monthLengths[month - 1] ?? 0;
}

function readDateTime(value: unknown, path: string): string {
  const dateTime = readString(value, path);
  const match = DATE_TIME_PATTERN.exec(dateTime);

  if (match === null) {
    return invalidPracticeResponse(path);
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  const offsetHour = match[7] === undefined ? 0 : Number(match[7]);
  const offsetMinute = match[8] === undefined ? 0 : Number(match[8]);

  if (
    year < 1 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > getDaysInMonth(year, month) ||
    hour > 23 ||
    minute > 59 ||
    second > 59 ||
    offsetHour > 23 ||
    offsetMinute > 59 ||
    Number.isNaN(Date.parse(dateTime))
  ) {
    return invalidPracticeResponse(path);
  }

  return dateTime;
}

function parsePracticeCard(
  value: unknown,
  index: number,
  knownSequenceNumbers: Set<number>,
): PracticeCard {
  const path = `practice.cards[${index}]`;
  const card = readRecord(value, path);
  const sequenceNumber = readInteger(card.sequence_number, `${path}.sequence_number`);

  if (sequenceNumber < 1 || knownSequenceNumbers.has(sequenceNumber)) {
    return invalidPracticeResponse(`${path}.sequence_number`);
  }
  knownSequenceNumbers.add(sequenceNumber);

  return {
    sequenceNumber,
    promptText: readString(card.prompt_text, `${path}.prompt_text`),
    promptLanguage: readString(card.prompt_language, `${path}.prompt_language`),
    answerLanguage: readString(card.answer_language, `${path}.answer_language`),
  };
}

export function parsePracticeSession(value: unknown): PracticeSession {
  const session = readRecord(value, "practice");
  const promptSide = readCardSide(session.prompt_side, "practice.prompt_side");
  const answerSide = readCardSide(session.answer_side, "practice.answer_side");
  const totalCount = readInteger(session.total_count, "practice.total_count");
  const answeredCount = readInteger(session.answered_count, "practice.answered_count");
  const correctCount = readInteger(session.correct_count, "practice.correct_count");
  const wrongCount = readInteger(session.wrong_count, "practice.wrong_count");

  if (!Array.isArray(session.cards)) {
    return invalidPracticeResponse("practice.cards");
  }
  if (promptSide === answerSide) {
    return invalidPracticeResponse("practice.answer_side");
  }
  if (totalCount < 1) {
    return invalidPracticeResponse("practice.total_count");
  }
  if (answeredCount < 0 || answeredCount > totalCount) {
    return invalidPracticeResponse("practice.answered_count");
  }
  if (correctCount < 0 || correctCount > answeredCount) {
    return invalidPracticeResponse("practice.correct_count");
  }
  if (wrongCount < 0 || correctCount + wrongCount !== answeredCount) {
    return invalidPracticeResponse("practice.wrong_count");
  }
  if (session.cards.length !== totalCount - answeredCount) {
    return invalidPracticeResponse("practice.cards");
  }

  const knownSequenceNumbers = new Set<number>();
  const cards = session.cards.map((card, index) =>
    parsePracticeCard(card, index, knownSequenceNumbers),
  );

  for (let index = 1; index < cards.length; index += 1) {
    const previousCard = cards[index - 1];
    const card = cards[index];
    if (
      previousCard !== undefined &&
      card !== undefined &&
      card.sequenceNumber < previousCard.sequenceNumber
    ) {
      return invalidPracticeResponse(`practice.cards[${index}].sequence_number`);
    }
  }

  return {
    uuid: readUuid(session.training_session_uuid, "practice.training_session_uuid"),
    deckUuid: readUuid(session.deck_uuid, "practice.deck_uuid"),
    promptSide,
    answerSide,
    totalCount,
    answeredCount,
    correctCount,
    wrongCount,
    startedAt: readDateTime(session.started_at, "practice.started_at"),
    cards,
  };
}

export function parsePracticeActivityResponse(value: unknown): PracticeActivityResponse {
  const response = readRecord(value, "practiceActivity");

  return {
    trackerUuid: readNullableUuid(response.tracker_uuid, "practiceActivity.tracker_uuid"),
  };
}

export function parsePracticeDeckSummary(value: unknown): PracticeDeckSummary {
  const deck = readRecord(value, "practiceDeck");
  const wordsCount = readInteger(deck.words_count, "practiceDeck.words_count");

  if (wordsCount < 0) {
    return invalidPracticeResponse("practiceDeck.words_count");
  }

  return {
    uuid: readUuid(deck.uuid, "practiceDeck.uuid"),
    wordsCount,
  };
}

function parsePracticeHistorySession(value: unknown, index: number): PracticeHistorySession {
  const path = `practiceHistory.items[${index}]`;
  const session = readRecord(value, path);
  const requestedCount = readInteger(session.requested_count, `${path}.requested_count`);
  const actualCount = readInteger(session.actual_count, `${path}.actual_count`);
  const correctCount = readInteger(session.correct_count, `${path}.correct_count`);
  const wrongCount = readInteger(session.wrong_count, `${path}.wrong_count`);
  const promptSide = readCardSide(session.prompt_side, `${path}.prompt_side`);
  const answerSide = readCardSide(session.answer_side, `${path}.answer_side`);
  const finishedAtValue = readNullableString(session.finished_at, `${path}.finished_at`);
  const finishedAt =
    finishedAtValue === null ? null : readDateTime(finishedAtValue, `${path}.finished_at`);
  const status = readTrainingSessionStatus(session.status, `${path}.status`);

  if (
    requestedCount < 0 ||
    actualCount < 0 ||
    actualCount > requestedCount ||
    correctCount < 0 ||
    wrongCount < 0 ||
    correctCount + wrongCount !== actualCount
  ) {
    return invalidPracticeResponse(`${path}.counts`);
  }
  if (promptSide === answerSide) {
    return invalidPracticeResponse(`${path}.answer_side`);
  }

  return {
    uuid: readUuid(session.uuid, `${path}.uuid`),
    deckUuid: readUuid(session.deck_uuid, `${path}.deck_uuid`),
    status,
    requestedCount,
    actualCount,
    correctCount,
    wrongCount,
    promptSide,
    answerSide,
    startedAt: readDateTime(session.started_at, `${path}.started_at`),
    finishedAt,
  };
}

export function parsePracticeHistoryPage(value: unknown): PracticeHistoryPage {
  const page = readRecord(value, "practiceHistory");
  if (!Array.isArray(page.items)) {
    return invalidPracticeResponse("practiceHistory.items");
  }

  const sessions = page.items.map(parsePracticeHistorySession);
  const knownSessionUuids = new Set<string>();
  sessions.forEach((session, index) => {
    if (knownSessionUuids.has(session.uuid)) {
      return invalidPracticeResponse(`practiceHistory.items[${index}].uuid`);
    }
    knownSessionUuids.add(session.uuid);
  });

  const nextCursor = readNullableString(page.next_cursor, "practiceHistory.next_cursor");
  const hasMore = readBoolean(page.has_more, "practiceHistory.has_more");
  if (hasMore !== (nextCursor !== null) || nextCursor === "") {
    return invalidPracticeResponse("practiceHistory.next_cursor");
  }

  return { sessions, nextCursor, hasMore };
}

function parsePracticeSessionHistoryItem(
  value: unknown,
  index: number,
): PracticeSessionHistoryItem {
  const path = `practiceSessionHistory[${index}]`;
  const item = readRecord(value, path);
  const sequenceNumber = readInteger(item.sequence_number, `${path}.sequence_number`);
  const isAnswered = readBoolean(item.is_answered, `${path}.is_answered`);
  const isCorrect = readNullableBoolean(item.is_correct, `${path}.is_correct`);
  const userTypedText = readNullableString(item.user_typed_text, `${path}.user_typed_text`);

  if (sequenceNumber < 1) {
    return invalidPracticeResponse(`${path}.sequence_number`);
  }
  if (isAnswered !== (isCorrect !== null)) {
    return invalidPracticeResponse(`${path}.is_correct`);
  }
  if ((!isAnswered && userTypedText !== null) || (userTypedText === null && isCorrect === true)) {
    return invalidPracticeResponse(`${path}.user_typed_text`);
  }

  return {
    itemUuid: readUuid(item.item_uuid, `${path}.item_uuid`),
    sequenceNumber,
    promptText: readString(item.prompt_text, `${path}.prompt_text`),
    answerText: readString(item.answer_text, `${path}.answer_text`),
    promptLanguage: readString(item.prompt_lang, `${path}.prompt_lang`),
    answerLanguage: readString(item.answer_lang, `${path}.answer_lang`),
    userTypedText,
    isAnswered,
    isCorrect,
  };
}

export function parsePracticeSessionHistory(value: unknown): readonly PracticeSessionHistoryItem[] {
  if (!Array.isArray(value)) {
    return invalidPracticeResponse("practiceSessionHistory");
  }

  const items = value.map(parsePracticeSessionHistoryItem);
  const knownItemUuids = new Set<string>();
  const knownSequenceNumbers = new Set<number>();

  items.forEach((item, index) => {
    if (knownItemUuids.has(item.itemUuid)) {
      return invalidPracticeResponse(`practiceSessionHistory[${index}].item_uuid`);
    }
    if (knownSequenceNumbers.has(item.sequenceNumber)) {
      return invalidPracticeResponse(`practiceSessionHistory[${index}].sequence_number`);
    }

    knownItemUuids.add(item.itemUuid);
    knownSequenceNumbers.add(item.sequenceNumber);
  });

  return items;
}

export function parseSubmitPracticeAnswerResult(value: unknown): SubmitPracticeAnswerResult {
  const result = readRecord(value, "practiceAnswer");
  const isCorrect = readBoolean(result.is_correct, "practiceAnswer.is_correct");
  const answeredCount = readInteger(result.answered_count, "practiceAnswer.answered_count");
  const correctCount = readInteger(result.correct_count, "practiceAnswer.correct_count");
  const totalCount = readInteger(result.total_count, "practiceAnswer.total_count");
  const isFinished = readBoolean(result.is_finished, "practiceAnswer.is_finished");
  const timeToComplete = readNullableInteger(
    result.time_to_complete,
    "practiceAnswer.time_to_complete",
  );

  if (totalCount < 1) {
    return invalidPracticeResponse("practiceAnswer.total_count");
  }
  if (answeredCount < 1 || answeredCount > totalCount) {
    return invalidPracticeResponse("practiceAnswer.answered_count");
  }
  if (correctCount < 0 || correctCount > answeredCount) {
    return invalidPracticeResponse("practiceAnswer.correct_count");
  }
  if (isCorrect ? correctCount < 1 : correctCount === answeredCount) {
    return invalidPracticeResponse("practiceAnswer.is_correct");
  }
  if (isFinished !== (answeredCount === totalCount)) {
    return invalidPracticeResponse("practiceAnswer.is_finished");
  }
  if (
    (isFinished && (timeToComplete === null || timeToComplete < 0)) ||
    (!isFinished && timeToComplete !== null)
  ) {
    return invalidPracticeResponse("practiceAnswer.time_to_complete");
  }

  return {
    isCorrect,
    answerText: readString(result.answer_text, "practiceAnswer.answer_text"),
    answeredCount,
    correctCount,
    totalCount,
    isFinished,
    timeToCompleteSeconds: timeToComplete,
  };
}
