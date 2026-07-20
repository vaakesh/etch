import { ApiError } from "../../../api";
import type { LibraryDeck, LibraryDeckPage, LibraryPreviewCard } from "./library-types";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function invalidLibraryResponse(path: string): never {
  throw new ApiError({
    status: 0,
    code: "INVALID_LIBRARY_RESPONSE",
    message: `The backend returned an unexpected library value at ${path}.`,
  });
}

function readRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return invalidLibraryResponse(path);
  }

  return value as Record<string, unknown>;
}

function readString(value: unknown, path: string): string {
  if (typeof value !== "string") {
    return invalidLibraryResponse(path);
  }

  return value;
}

function readNullableString(value: unknown, path: string): string | null {
  if (value === null) {
    return null;
  }

  return readString(value, path);
}

function readBoolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") {
    return invalidLibraryResponse(path);
  }

  return value;
}

function readInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value)) {
    return invalidLibraryResponse(path);
  }

  return value;
}

function readUuid(value: unknown, path: string): string {
  const uuid = readString(value, path);

  if (!UUID_PATTERN.test(uuid)) {
    return invalidLibraryResponse(path);
  }

  return uuid;
}

function readNullableDateTime(value: unknown, path: string): string | null {
  const dateTime = readNullableString(value, path);

  if (dateTime !== null && Number.isNaN(Date.parse(dateTime))) {
    return invalidLibraryResponse(path);
  }

  return dateTime;
}

function parsePreviewCard(value: unknown, path: string): LibraryPreviewCard {
  const card = readRecord(value, path);

  return {
    uuid: readUuid(card.uuid, `${path}.uuid`),
    frontText: readString(card.front_text, `${path}.front_text`),
    backText: readString(card.back_text, `${path}.back_text`),
  };
}

function parseDeck(value: unknown, index: number): LibraryDeck {
  const path = `decks[${index}]`;
  const deck = readRecord(value, path);
  const totalWordsCount = readInteger(
    deck.deck_total_words_count,
    `${path}.deck_total_words_count`,
  );
  const accuracy = readInteger(deck.user_accuracy, `${path}.user_accuracy`);

  if (!Array.isArray(deck.cards)) {
    return invalidLibraryResponse(`${path}.cards`);
  }

  if (totalWordsCount < 0) {
    return invalidLibraryResponse(`${path}.deck_total_words_count`);
  }
  if (accuracy < 0 || accuracy > 100) {
    return invalidLibraryResponse(`${path}.user_accuracy`);
  }

  return {
    uuid: readUuid(deck.uuid, `${path}.uuid`),
    title: readString(deck.title, `${path}.title`),
    description: readNullableString(deck.description, `${path}.description`),
    totalWordsCount,
    accuracy,
    isFavourite: readBoolean(deck.is_favourite, `${path}.is_favourite`),
    updatedAt: readNullableDateTime(deck.updated_at, `${path}.updated_at`),
    cards: deck.cards.map((card, cardIndex) =>
      parsePreviewCard(card, `${path}.cards[${cardIndex}]`),
    ),
  };
}

export function parseLibraryDeckPage(value: unknown): LibraryDeckPage {
  const page = readRecord(value, "library");

  if (!Array.isArray(page.decks)) {
    return invalidLibraryResponse("decks");
  }

  const nextCursor = readNullableString(page.next_cursor, "next_cursor");
  const hasMore = readBoolean(page.has_more, "has_more");

  if (hasMore && (nextCursor === null || nextCursor.length === 0)) {
    return invalidLibraryResponse("next_cursor");
  }
  if (!hasMore && nextCursor !== null) {
    return invalidLibraryResponse("next_cursor");
  }

  return {
    decks: page.decks.map(parseDeck),
    nextCursor,
    hasMore,
  };
}
