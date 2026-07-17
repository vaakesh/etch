import { ApiError } from "../../../api";
import type { HomeDashboard, HomeDeck, HomeProgress } from "./home-types";

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

function parseDeck(value: unknown, index: number): HomeDeck {
  const path = `decks[${index}]`;
  const deck = readRecord(value, path);

  return {
    title: readString(deck.title, `${path}.title`),
    description: readNullableString(deck.description, `${path}.description`),
    totalWordsCount: readInteger(deck.deck_total_words_count, `${path}.deck_total_words_count`),
    accuracy: readInteger(deck.user_accuracy, `${path}.user_accuracy`),
    updatedAt: readNullableDateTime(deck.updated_at, `${path}.updated_at`),
  };
}

function parseProgress(value: unknown): HomeProgress {
  const progress = readRecord(value, "progress");

  return {
    wordsExplored: readInteger(progress.user_words_explored, "progress.user_words_explored"),
    weeklyAccuracy: readFiniteNumber(
      progress.user_weekly_accuracy,
      "progress.user_weekly_accuracy",
    ),
    currentStreakDays: readInteger(progress.user_current_streak, "progress.user_current_streak"),
    totalStudyTimeSeconds: readInteger(
      progress.user_total_study_time,
      "progress.user_total_study_time",
    ),
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
    weeklyActivity: dashboard.user_weekly_activity.map((value, index) =>
      readInteger(value, `user_weekly_activity[${index}]`),
    ),
  };
}
