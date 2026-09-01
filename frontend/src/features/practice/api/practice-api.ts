import { ApiError, apiFetch } from "../../../api";
import {
  parsePracticeDeckSummary,
  parsePracticeActivityResponse,
  parsePracticeHistoryPage,
  parsePracticeSession,
  parsePracticeSessionHistory,
  parseSubmitPracticeAnswerResult,
} from "../model/practice-contract";
import type {
  PracticeHistoryFilter,
  PracticeActivityInput,
  PracticeActivityResponse,
  PracticeHistorySession,
  PracticeDeckSummary,
  PracticeSession,
  PracticeSessionHistoryItem,
  StartPracticeSessionInput,
  SubmitPracticeAnswerInput,
  SubmitPracticeAnswerResult,
} from "../model/practice-types";

const PRACTICE_HISTORY_PAGE_SIZE = 100;
const PRACTICE_SESSION_HISTORY_PAGE_SIZE = 100;

interface RecordPracticeActivityOptions {
  keepalive?: boolean;
}

function assertExpectedUuid(expectedUuid: string, actualUuid: string, resource: string): void {
  if (actualUuid.toLowerCase() !== expectedUuid.toLowerCase()) {
    throw new ApiError({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
      message: `The backend returned ${resource} with an unexpected UUID.`,
    });
  }
}

export async function validatePracticeDeck(
  deckUuid: string,
  signal?: AbortSignal,
): Promise<PracticeDeckSummary> {
  const payload = await apiFetch<unknown>(`/decks/${deckUuid}`, { signal });
  const deck = parsePracticeDeckSummary(payload);

  assertExpectedUuid(deckUuid, deck.uuid, "a different deck");
  return deck;
}

export async function getPracticeSessionHistory(
  filter: PracticeHistoryFilter,
  signal?: AbortSignal,
): Promise<readonly PracticeHistorySession[]> {
  const sessions: PracticeHistorySession[] = [];
  const knownSessionUuids = new Set<string>();
  const requestedCursors = new Set<string | null>();
  let cursor: string | null = null;

  do {
    if (requestedCursors.has(cursor)) {
      throw new ApiError({
        status: 0,
        code: "INVALID_PRACTICE_RESPONSE",
        message: "The backend repeated a practice-history pagination cursor.",
      });
    }
    requestedCursors.add(cursor);

    const payload = await apiFetch<unknown>("/users/me/training-sessions", {
      query: {
        cursor,
        limit: PRACTICE_HISTORY_PAGE_SIZE,
        status: filter === "all" ? null : filter,
      },
      signal,
    });
    const page = parsePracticeHistoryPage(payload);

    if (filter !== "all" && page.sessions.some((session) => session.status !== filter)) {
      throw new ApiError({
        status: 0,
        code: "INVALID_PRACTICE_RESPONSE",
        message: "The backend returned a practice-history session outside the requested filter.",
      });
    }

    page.sessions.forEach((session) => {
      if (!knownSessionUuids.has(session.uuid)) {
        knownSessionUuids.add(session.uuid);
        sessions.push(session);
      }
    });
    cursor = page.hasMore ? page.nextCursor : null;
  } while (cursor !== null);

  return sessions;
}

export async function getPracticeSessionItemsHistory(
  sessionUuid: string,
  signal?: AbortSignal,
): Promise<readonly PracticeSessionHistoryItem[]> {
  const items: PracticeSessionHistoryItem[] = [];
  const knownItemUuids = new Set<string>();
  const knownSequenceNumbers = new Set<number>();
  let pageNumber = 1;

  while (true) {
    const payload = await apiFetch<unknown>(`/training-sessions/${sessionUuid}/history`, {
      query: { ps: PRACTICE_SESSION_HISTORY_PAGE_SIZE, pn: pageNumber },
      signal,
    });
    const page = parsePracticeSessionHistory(payload);

    page.forEach((item) => {
      if (knownItemUuids.has(item.itemUuid) || knownSequenceNumbers.has(item.sequenceNumber)) {
        throw new ApiError({
          status: 0,
          code: "INVALID_PRACTICE_RESPONSE",
          message: "The backend repeated an item in the practice-session history.",
        });
      }

      knownItemUuids.add(item.itemUuid);
      knownSequenceNumbers.add(item.sequenceNumber);
      items.push(item);
    });

    if (page.length < PRACTICE_SESSION_HISTORY_PAGE_SIZE) {
      break;
    }
    pageNumber += 1;
  }

  return items.sort((left, right) => left.sequenceNumber - right.sequenceNumber);
}

export async function startPracticeSession(
  deckUuid: string,
  input: StartPracticeSessionInput,
  signal?: AbortSignal,
): Promise<PracticeSession> {
  const payload = await apiFetch<unknown>(`/bff/practice/${deckUuid}/start`, {
    method: "POST",
    body: {
      prompt_side: input.promptSide,
      words_per_session: input.wordsPerSession,
    },
    signal,
  });
  const session = parsePracticeSession(payload);

  assertExpectedUuid(deckUuid, session.deckUuid, "a practice session for a different deck");
  if (
    session.promptSide !== input.promptSide ||
    session.totalCount > input.wordsPerSession ||
    session.answeredCount !== 0 ||
    session.correctCount !== 0 ||
    session.wrongCount !== 0
  ) {
    throw new ApiError({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
      message: "The backend returned an unexpected newly started practice session.",
    });
  }
  return session;
}

export async function resumePracticeSession(
  sessionUuid: string,
  signal?: AbortSignal,
): Promise<PracticeSession> {
  const payload = await apiFetch<unknown>(`/bff/practice/${sessionUuid}/resume`, { signal });
  const session = parsePracticeSession(payload);

  assertExpectedUuid(sessionUuid, session.uuid, "a different practice session");
  if (session.answeredCount >= session.totalCount || session.cards.length === 0) {
    throw new ApiError({
      status: 0,
      code: "INVALID_PRACTICE_RESPONSE",
      message: "The backend returned a finished practice session from the resume endpoint.",
    });
  }
  return session;
}

export async function submitPracticeAnswer(
  sessionUuid: string,
  sequenceNumber: number,
  input: SubmitPracticeAnswerInput,
  signal?: AbortSignal,
): Promise<SubmitPracticeAnswerResult> {
  const body =
    input.action === "answer"
      ? { action: input.action, answer: input.answer }
      : { action: input.action };
  const payload = await apiFetch<unknown>(
    `/training-sessions/${sessionUuid}/items/${sequenceNumber}/submit`,
    {
      method: "PUT",
      body,
      signal,
    },
  );

  return parseSubmitPracticeAnswerResult(payload);
}

export async function recordPracticeActivity(
  sessionUuid: string,
  input: PracticeActivityInput,
  options: RecordPracticeActivityOptions = {},
): Promise<PracticeActivityResponse> {
  const body =
    input.event === "resume"
      ? { event: input.event }
      : { event: input.event, tracker_uuid: input.trackerUuid };
  const payload = await apiFetch<unknown>(`/training-sessions/${sessionUuid}/activity`, {
    method: "POST",
    body,
    keepalive: options.keepalive,
  });

  return parsePracticeActivityResponse(payload);
}
