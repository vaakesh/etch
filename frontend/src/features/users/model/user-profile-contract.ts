import { ApiError } from "../../../api";
import type { UserProfile, UserProfileDeck, UserProfileDeckPage } from "./user-profile-types";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function invalidUserProfileResponse(path: string): never {
  throw new ApiError({
    status: 0,
    code: "INVALID_USER_PROFILE_RESPONSE",
    message: `The backend returned an unexpected user profile value at ${path}.`,
  });
}

function readRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return invalidUserProfileResponse(path);
  }

  return value as Record<string, unknown>;
}

function readString(value: unknown, path: string): string {
  if (typeof value !== "string") {
    return invalidUserProfileResponse(path);
  }

  return value;
}

function readUuid(value: unknown, path: string): string {
  const uuid = readString(value, path);
  if (!UUID_PATTERN.test(uuid)) {
    return invalidUserProfileResponse(path);
  }

  return uuid;
}

function readNonNegativeInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    return invalidUserProfileResponse(path);
  }

  return value;
}

function readBoolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") {
    return invalidUserProfileResponse(path);
  }

  return value;
}

function readNullableString(value: unknown, path: string): string | null {
  return value === null ? null : readString(value, path);
}

function readDateTime(value: unknown, path: string): string {
  const dateTime = readString(value, path);
  if (Number.isNaN(Date.parse(dateTime))) {
    return invalidUserProfileResponse(path);
  }

  return dateTime;
}

function readNullableDateTime(value: unknown, path: string): string | null {
  const dateTime = readNullableString(value, path);
  if (dateTime !== null && Number.isNaN(Date.parse(dateTime))) {
    return invalidUserProfileResponse(path);
  }

  return dateTime;
}

function parseUserProfileDeck(value: unknown, index: number): UserProfileDeck {
  const path = `userDecks.items[${index}]`;
  const deck = readRecord(value, path);

  return {
    uuid: readUuid(deck.uuid, `${path}.uuid`),
    ownerUuid: readUuid(deck.owner_uuid, `${path}.owner_uuid`),
    ownerUsername: readString(deck.owner_username, `${path}.owner_username`),
    title: readString(deck.title, `${path}.title`),
    description: readNullableString(deck.description, `${path}.description`),
    totalWordsCount: readNonNegativeInteger(deck.words_count, `${path}.words_count`),
    savesCount: readNonNegativeInteger(deck.saves_count, `${path}.saves_count`),
    isSaved: false,
    isPublic: readBoolean(deck.is_public, `${path}.is_public`),
    updatedAt: readNullableDateTime(deck.updated_at, `${path}.updated_at`),
  };
}

export function parseUserProfile(value: unknown): UserProfile {
  const profile = readRecord(value, "profile");

  return {
    uuid: readUuid(profile.uuid, "profile.uuid"),
    username: readString(profile.username, "profile.username"),
    createdAt: readDateTime(profile.created_at, "profile.created_at"),
    deckCount: readNonNegativeInteger(profile.deck_count, "profile.deck_count"),
    totalSavesCount: readNonNegativeInteger(profile.total_saves_count, "profile.total_saves_count"),
  };
}

export function parseUserProfileDeckPage(value: unknown): UserProfileDeckPage {
  const page = readRecord(value, "userDecks");
  if (!Array.isArray(page.items)) {
    return invalidUserProfileResponse("userDecks.items");
  }

  const nextCursor = readNullableString(page.next_cursor, "userDecks.next_cursor");
  const hasMore = readBoolean(page.has_more, "userDecks.has_more");
  if (hasMore && (nextCursor === null || nextCursor.length === 0)) {
    return invalidUserProfileResponse("userDecks.next_cursor");
  }
  if (!hasMore && nextCursor !== null) {
    return invalidUserProfileResponse("userDecks.next_cursor");
  }

  return {
    decks: page.items.map(parseUserProfileDeck),
    nextCursor,
    hasMore,
  };
}
