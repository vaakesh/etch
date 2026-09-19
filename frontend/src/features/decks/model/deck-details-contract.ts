import { ApiError } from "../../../api";
import type { DeckDetails, DeckDetailsCard, DeckDetailsCardBatch } from "./deck-details-types";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function invalidDeckDetailsResponse(path: string): never {
  throw new ApiError({
    status: 0,
    code: "INVALID_DECK_DETAILS_RESPONSE",
    message: `The backend returned an unexpected deck-details value at ${path}.`,
  });
}

function readRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return invalidDeckDetailsResponse(path);
  }

  return value as Record<string, unknown>;
}

function readString(value: unknown, path: string): string {
  if (typeof value !== "string") {
    return invalidDeckDetailsResponse(path);
  }

  return value;
}

function readUuid(value: unknown, path: string): string {
  const uuid = readString(value, path);
  if (!UUID_PATTERN.test(uuid)) {
    return invalidDeckDetailsResponse(path);
  }

  return uuid;
}

function readNullableString(value: unknown, path: string): string | null {
  return value === null ? null : readString(value, path);
}

function readBoolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") {
    return invalidDeckDetailsResponse(path);
  }

  return value;
}

function readNonNegativeInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    return invalidDeckDetailsResponse(path);
  }

  return value;
}

function readNullableDateTime(value: unknown, path: string): string | null {
  const dateTime = readNullableString(value, path);
  if (dateTime !== null && Number.isNaN(Date.parse(dateTime))) {
    return invalidDeckDetailsResponse(path);
  }

  return dateTime;
}

function readDateTime(value: unknown, path: string): string {
  const dateTime = readString(value, path);
  if (Number.isNaN(Date.parse(dateTime))) {
    return invalidDeckDetailsResponse(path);
  }

  return dateTime;
}

export function parseDeckDetails(value: unknown): DeckDetails {
  const deck = readRecord(value, "deck");

  return {
    uuid: readUuid(deck.uuid, "deck.uuid"),
    ownerUuid: readUuid(deck.owner_uuid, "deck.owner_uuid"),
    ownerUsername: readString(deck.owner_username, "deck.owner_username"),
    title: readString(deck.title, "deck.title"),
    description: readNullableString(deck.description, "deck.description"),
    totalWordsCount: readNonNegativeInteger(deck.words_count, "deck.words_count"),
    savesCount: readNonNegativeInteger(deck.saves_count, "deck.saves_count"),
    isPublic: readBoolean(deck.is_public, "deck.is_public"),
    updatedAt: readNullableDateTime(deck.updated_at, "deck.updated_at"),
  };
}

function parseDeckDetailsCard(value: unknown, index: number): DeckDetailsCard {
  const path = `deckCards[${index}]`;
  const card = readRecord(value, path);

  return {
    uuid: readUuid(card.uuid, `${path}.uuid`),
    frontText: readString(card.front_text, `${path}.front_text`),
    backText: readString(card.back_text, `${path}.back_text`),
    frontLang: readString(card.front_lang, `${path}.front_lang`),
    backLang: readString(card.back_lang, `${path}.back_lang`),
    updatedAt: readDateTime(card.updated_at, `${path}.updated_at`),
  };
}

export function parseDeckDetailsCardResponse(value: unknown): DeckDetailsCard {
  return parseDeckDetailsCard(value, 0);
}

export function parseDeckDetailsCardBatch(
  value: unknown,
  offset: number,
  limit: number,
): DeckDetailsCardBatch {
  if (!Array.isArray(value) || value.length > limit) {
    return invalidDeckDetailsResponse("deckCards");
  }

  const cards = value.map(parseDeckDetailsCard);

  return {
    cards,
    offset,
    hasMore: cards.length === limit,
  };
}
