import { ApiError } from "../../../api";
import type { CardSide } from "../../practice/model/practice-types";
import type { ActiveReviewSession, ReviewSideSummary, ReviewSummary } from "./review-types";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const DATE_TIME_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

function invalidReviewResponse(path: string): never {
  throw new ApiError({
    status: 0,
    code: "INVALID_REVIEW_RESPONSE",
    message: `The backend returned an unexpected review value at ${path}.`,
  });
}

function readRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return invalidReviewResponse(path);
  }

  return value as Record<string, unknown>;
}

function readCount(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    return invalidReviewResponse(path);
  }

  return value;
}

function readNullableDateTime(value: unknown, path: string): string | null {
  if (value === null) {
    return null;
  }
  if (
    typeof value !== "string" ||
    !DATE_TIME_PATTERN.test(value) ||
    Number.isNaN(Date.parse(value))
  ) {
    return invalidReviewResponse(path);
  }

  return value;
}

function readCardSide(value: unknown, path: string): CardSide {
  if (value !== "front" && value !== "back") {
    return invalidReviewResponse(path);
  }

  return value;
}

function parseSide(value: unknown, path: string): ReviewSideSummary {
  const side = readRecord(value, path);
  const dueNow = readCount(side.due_now, `${path}.due_now`);
  const dueToday = readCount(side.due_today, `${path}.due_today`);

  // due_today включает due_now: обратное означает рассинхрон с backend
  if (dueNow > dueToday) {
    return invalidReviewResponse(`${path}.due_now`);
  }

  return {
    dueNow,
    dueToday,
    nextDueAt: readNullableDateTime(side.next_due_at, `${path}.next_due_at`),
  };
}

function parseActiveSession(value: unknown): ActiveReviewSession | null {
  if (value === null) {
    return null;
  }

  const path = "reviewSummary.active_session";
  const session = readRecord(value, path);
  const uuid = session.training_session_uuid;
  const answeredCount = readCount(session.answered_count, `${path}.answered_count`);
  const totalCount = readCount(session.total_count, `${path}.total_count`);

  if (typeof uuid !== "string" || !UUID_PATTERN.test(uuid)) {
    return invalidReviewResponse(`${path}.training_session_uuid`);
  }
  if (totalCount < 1 || answeredCount > totalCount) {
    return invalidReviewResponse(`${path}.answered_count`);
  }

  return {
    uuid: uuid.toLowerCase(),
    promptSide: readCardSide(session.prompt_side, `${path}.prompt_side`),
    answeredCount,
    totalCount,
  };
}

export function parseReviewSummary(value: unknown): ReviewSummary {
  const summary = readRecord(value, "reviewSummary");
  const sides = readRecord(summary.sides, "reviewSummary.sides");

  if (typeof summary.timezone !== "string" || summary.timezone.length === 0) {
    return invalidReviewResponse("reviewSummary.timezone");
  }

  return {
    timezone: summary.timezone,
    sides: {
      front: parseSide(sides.front, "reviewSummary.sides.front"),
      back: parseSide(sides.back, "reviewSummary.sides.back"),
    },
    activeSession: parseActiveSession(summary.active_session),
  };
}
