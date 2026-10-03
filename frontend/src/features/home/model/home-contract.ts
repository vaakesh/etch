import { ApiError } from "../../../api";
import type { HomeDashboard, HomeDeck, HomeProgress, HomeWeeklyActivityDay } from "./home-types";

const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function invalidHomeResponse(path: string): never {
  throw new ApiError({
    status: 0,
    code: "INVALID_HOME_RESPONSE",
    message: `The backend returned an unexpected home dashboard value at ${path}.`,
  });
}

function readRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return invalidHomeResponse(path);
  }

  return value as Record<string, unknown>;
}

function readString(value: unknown, path: string): string {
  if (typeof value !== "string") {
    return invalidHomeResponse(path);
  }

  return value;
}

function readUuid(value: unknown, path: string): string {
  const uuid = readString(value, path);

  if (!UUID_PATTERN.test(uuid)) {
    return invalidHomeResponse(path);
  }

  return uuid;
}

function readNullableString(value: unknown, path: string): string | null {
  if (value === null) {
    return null;
  }

  return readString(value, path);
}

function readFiniteNumber(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return invalidHomeResponse(path);
  }

  return value;
}

function readInteger(value: unknown, path: string): number {
  const number = readFiniteNumber(value, path);
  if (!Number.isInteger(number)) {
    return invalidHomeResponse(path);
  }

  return number;
}

function readNullableDateTime(value: unknown, path: string): string | null {
  const dateTime = readNullableString(value, path);
  if (dateTime !== null && Number.isNaN(Date.parse(dateTime))) {
    return invalidHomeResponse(path);
  }

  return dateTime;
}

function readDateOnly(value: unknown, path: string): string {
  const date = readString(value, path);
  const match = DATE_ONLY_PATTERN.exec(date);

  if (match === null) {
    return invalidHomeResponse(path);
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsedDate = new Date(Date.UTC(year, month - 1, day));

  if (
    parsedDate.getUTCFullYear() !== year ||
    parsedDate.getUTCMonth() !== month - 1 ||
    parsedDate.getUTCDate() !== day
  ) {
    return invalidHomeResponse(path);
  }

  return date;
}

function parseWeeklyActivityDay(value: unknown, index: number): HomeWeeklyActivityDay {
  const path = `user_weekly_activity[${index}]`;
  const activityDay = readRecord(value, path);
  const activityValue = readInteger(activityDay.value, `${path}.value`);

  if (activityValue < 0) {
    return invalidHomeResponse(`${path}.value`);
  }

  return {
    date: readDateOnly(activityDay.date, `${path}.date`),
    value: activityValue,
  };
}

function parseDeck(value: unknown, index: number): HomeDeck {
  const path = `decks[${index}]`;
  const deck = readRecord(value, path);
  const totalWordsCount = readInteger(deck.words_count, `${path}.words_count`);
  const accuracy = readInteger(deck.user_accuracy, `${path}.user_accuracy`);

  if (totalWordsCount < 0) {
    return invalidHomeResponse(`${path}.words_count`);
  }
  if (accuracy < 0 || accuracy > 100) {
    return invalidHomeResponse(`${path}.user_accuracy`);
  }

  return {
    uuid: readUuid(deck.uuid, `${path}.uuid`),
    ownerUuid: readUuid(deck.owner_uuid, `${path}.owner_uuid`),
    title: readString(deck.title, `${path}.title`),
    description: readNullableString(deck.description, `${path}.description`),
    totalWordsCount,
    accuracy,
    updatedAt: readNullableDateTime(deck.updated_at, `${path}.updated_at`),
  };
}

function parseProgress(value: unknown): HomeProgress {
  const progress = readRecord(value, "progress");
  const wordsExplored = readInteger(progress.user_words_explored, "progress.user_words_explored");
  const weeklyAccuracy = readInteger(
    progress.user_weekly_accuracy,
    "progress.user_weekly_accuracy",
  );
  const currentStreakDays = readInteger(
    progress.user_current_streak,
    "progress.user_current_streak",
  );
  const totalStudyTimeSeconds = readInteger(
    progress.user_total_study_time,
    "progress.user_total_study_time",
  );

  if (wordsExplored < 0) {
    return invalidHomeResponse("progress.user_words_explored");
  }
  if (weeklyAccuracy < 0 || weeklyAccuracy > 100) {
    return invalidHomeResponse("progress.user_weekly_accuracy");
  }
  if (currentStreakDays < 0) {
    return invalidHomeResponse("progress.user_current_streak");
  }
  if (totalStudyTimeSeconds < 0) {
    return invalidHomeResponse("progress.user_total_study_time");
  }

  return {
    wordsExplored,
    weeklyAccuracy,
    currentStreakDays,
    totalStudyTimeSeconds,
  };
}

export function parseHomeDashboard(value: unknown): HomeDashboard {
  const dashboard = readRecord(value, "home");

  if (!Array.isArray(dashboard.decks)) {
    return invalidHomeResponse("decks");
  }
  if (!Array.isArray(dashboard.user_weekly_activity)) {
    return invalidHomeResponse("user_weekly_activity");
  }

  return {
    decks: dashboard.decks.map(parseDeck),
    progress: parseProgress(dashboard.progress),
    weeklyActivity: dashboard.user_weekly_activity.map(parseWeeklyActivityDay),
  };
}
