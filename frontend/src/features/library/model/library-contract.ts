import { ApiError } from "../../../api";
import type {
  CreatedLibraryCard,
  CreatedLibraryDeck,
  DeckCardPage,
  EditableLibraryCard,
  EditableLibraryDeck,
  LibraryCard,
  LibraryCardPage,
  LibraryDeck,
  LibraryDeckOption,
  LibraryDeckOptionPage,
  LibraryDeckPage,
  LibraryPreviewCard,
  UpdatedLibraryCard,
} from "./library-types";

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

function readDateTime(value: unknown, path: string): string {
  const dateTime = readString(value, path);

  if (Number.isNaN(Date.parse(dateTime))) {
    return invalidLibraryResponse(path);
  }

  return dateTime;
}

function parsePreviewCard(value: unknown, path: string): LibraryPreviewCard {
  const card = readRecord(value, path);

  return {
    uuid: readUuid(card.card_uuid, `${path}.card_uuid`),
    frontText: readString(card.front_text, `${path}.front_text`),
    backText: readString(card.back_text, `${path}.back_text`),
    sourceLang: readString(card.source_lang, `${path}.source_lang`),
    targetLang: readString(card.target_lang, `${path}.target_lang`),
    updatedAt: readDateTime(card.updated_at, `${path}.updated_at`),
  };
}

function parseLibraryCard(value: unknown, index: number): LibraryCard {
  const path = `cards[${index}]`;
  const card = readRecord(value, path);

  return {
    uuid: readUuid(card.card_uuid, `${path}.card_uuid`),
    frontText: readString(card.front_text, `${path}.front_text`),
    backText: readString(card.back_text, `${path}.back_text`),
    sourceLang: readString(card.source_lang, `${path}.source_lang`),
    targetLang: readString(card.target_lang, `${path}.target_lang`),
    updatedAt: readDateTime(card.updated_at, `${path}.updated_at`),
  };
}

function parseDeckCard(value: unknown, index: number): EditableLibraryCard {
  const path = `deckCards[${index}]`;
  const card = readRecord(value, path);

  return {
    uuid: readUuid(card.uuid, `${path}.uuid`),
    frontText: readString(card.front_text, `${path}.front_text`),
    backText: readString(card.back_text, `${path}.back_text`),
    sourceLang: readString(card.source_lang, `${path}.source_lang`),
    targetLang: readString(card.target_lang, `${path}.target_lang`),
  };
}

export function parseUpdatedLibraryCard(value: unknown): UpdatedLibraryCard {
  const card = readRecord(value, "card");

  return {
    uuid: readUuid(card.uuid, "card.uuid"),
    frontText: readString(card.front_text, "card.front_text"),
    backText: readString(card.back_text, "card.back_text"),
    sourceLang: readString(card.source_lang, "card.source_lang"),
    targetLang: readString(card.target_lang, "card.target_lang"),
  };
}

export function parseEditableLibraryDeck(value: unknown): EditableLibraryDeck {
  const deck = readRecord(value, "deck");
  const totalWordsCount = readInteger(deck.words_count, "deck.words_count");

  if (totalWordsCount < 0) {
    return invalidLibraryResponse("deck.words_count");
  }

  return {
    uuid: readUuid(deck.uuid, "deck.uuid"),
    title: readString(deck.title, "deck.title"),
    description: readNullableString(deck.description, "deck.description"),
    totalWordsCount,
    isPublic: readBoolean(deck.is_public, "deck.is_public"),
    updatedAt: readNullableDateTime(deck.updated_at, "deck.updated_at"),
  };
}

export function parseDeckCardPage(value: unknown, offset: number, limit: number): DeckCardPage {
  if (!Array.isArray(value) || value.length > limit) {
    return invalidLibraryResponse("deckCards");
  }

  const cards = value.map(parseDeckCard);

  return {
    cards,
    nextOffset: offset + cards.length,
    hasMore: cards.length === limit,
  };
}

export function parseCreatedLibraryCard(value: unknown): CreatedLibraryCard {
  const card = readRecord(value, "card");

  return {
    uuid: readUuid(card.uuid, "card.uuid"),
    frontText: readString(card.front_text, "card.front_text"),
    backText: readString(card.back_text, "card.back_text"),
    sourceLang: readString(card.source_lang, "card.source_lang"),
    targetLang: readString(card.target_lang, "card.target_lang"),
  };
}

export function parseCreatedLibraryDeck(value: unknown): CreatedLibraryDeck {
  const deck = readRecord(value, "deck");
  const totalWordsCount = readInteger(deck.words_count, "deck.words_count");

  if (totalWordsCount < 0) {
    return invalidLibraryResponse("deck.words_count");
  }

  return {
    uuid: readUuid(deck.uuid, "deck.uuid"),
    title: readString(deck.title, "deck.title"),
    description: readNullableString(deck.description, "deck.description"),
    totalWordsCount,
    isPublic: readBoolean(deck.is_public, "deck.is_public"),
    updatedAt: readNullableDateTime(deck.updated_at, "deck.updated_at"),
  };
}

function parseDeck(value: unknown, index: number): LibraryDeck {
  const path = `decks[${index}]`;
  const deck = readRecord(value, path);
  const totalWordsCount = readInteger(deck.deck_words_count, `${path}.deck_words_count`);
  const accuracy = readInteger(deck.user_accuracy, `${path}.user_accuracy`);

  if (!Array.isArray(deck.cards)) {
    return invalidLibraryResponse(`${path}.cards`);
  }

  if (totalWordsCount < 0) {
    return invalidLibraryResponse(`${path}.deck_words_count`);
  }
  if (accuracy < 0 || accuracy > 100) {
    return invalidLibraryResponse(`${path}.user_accuracy`);
  }

  return {
    uuid: readUuid(deck.deck_uuid, `${path}.deck_uuid`),
    ownerUuid: readUuid(deck.owner_uuid, `${path}.owner_uuid`),
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

function readCursorPage(
  value: unknown,
  path: string,
): { items: readonly unknown[]; nextCursor: string | null; hasMore: boolean } {
  const page = readRecord(value, path);
  const items = page.items;

  if (!Array.isArray(items)) {
    return invalidLibraryResponse(`${path}.items`);
  }

  const nextCursor = readNullableString(page.next_cursor, `${path}.next_cursor`);
  const hasMore = readBoolean(page.has_more, `${path}.has_more`);

  if (hasMore && (nextCursor === null || nextCursor.length === 0)) {
    return invalidLibraryResponse(`${path}.next_cursor`);
  }
  if (!hasMore && nextCursor !== null) {
    return invalidLibraryResponse(`${path}.next_cursor`);
  }

  return { items, nextCursor, hasMore };
}

export function parseLibraryDeckOptionPage(value: unknown): LibraryDeckOptionPage {
  const page = readCursorPage(value, "deckOptions");

  const decks: readonly LibraryDeckOption[] = page.items.map((item, index) => {
    const path = `deckOptions[${index}]`;
    const deck = readRecord(item, path);
    const totalWordsCount = readInteger(deck.words_count, `${path}.words_count`);

    if (totalWordsCount < 0) {
      return invalidLibraryResponse(`${path}.words_count`);
    }

    return {
      uuid: readUuid(deck.uuid, `${path}.uuid`),
      title: readString(deck.title, `${path}.title`),
      totalWordsCount,
    };
  });

  return { decks, nextCursor: page.nextCursor, hasMore: page.hasMore };
}

export function parseLibraryDeckPage(value: unknown): LibraryDeckPage {
  const page = readCursorPage(value, "library");

  return {
    decks: page.items.map(parseDeck),
    nextCursor: page.nextCursor,
    hasMore: page.hasMore,
  };
}

export function parseLibraryCardPage(value: unknown): LibraryCardPage {
  const page = readCursorPage(value, "cardLibrary");

  return {
    cards: page.items.map(parseLibraryCard),
    nextCursor: page.nextCursor,
    hasMore: page.hasMore,
  };
}
