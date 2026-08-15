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
  ImportLibraryCardsResult,
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
    uuid: readUuid(card.uuid, `${path}.uuid`),
    frontText: readString(card.front_text, `${path}.front_text`),
    backText: readString(card.back_text, `${path}.back_text`),
    frontLang: readString(card.front_lang, `${path}.front_lang`),
    backLang: readString(card.back_lang, `${path}.back_lang`),
    updatedAt: readDateTime(card.updated_at, `${path}.updated_at`),
  };
}

function parseLibraryCard(value: unknown, index: number): LibraryCard {
  const path = `cards[${index}]`;
  const item = readRecord(value, path);
  const cardPath = `${path}.card`;
  const card = readRecord(item.card, cardPath);

  return {
    uuid: readUuid(card.uuid, `${cardPath}.uuid`),
    frontText: readString(card.front_text, `${cardPath}.front_text`),
    backText: readString(card.back_text, `${cardPath}.back_text`),
    frontLang: readString(card.front_lang, `${cardPath}.front_lang`),
    backLang: readString(card.back_lang, `${cardPath}.back_lang`),
    updatedAt: readDateTime(card.updated_at, `${cardPath}.updated_at`),
  };
}

function parseDeckCard(value: unknown, index: number): EditableLibraryCard {
  const path = `deckCards[${index}]`;
  const card = readRecord(value, path);

  return {
    uuid: readUuid(card.uuid, `${path}.uuid`),
    frontText: readString(card.front_text, `${path}.front_text`),
    backText: readString(card.back_text, `${path}.back_text`),
    frontLang: readString(card.front_lang, `${path}.front_lang`),
    backLang: readString(card.back_lang, `${path}.back_lang`),
  };
}

export function parseUpdatedLibraryCard(value: unknown): UpdatedLibraryCard {
  const card = readRecord(value, "card");

  return {
    uuid: readUuid(card.uuid, "card.uuid"),
    frontText: readString(card.front_text, "card.front_text"),
    backText: readString(card.back_text, "card.back_text"),
    frontLang: readString(card.front_lang, "card.front_lang"),
    backLang: readString(card.back_lang, "card.back_lang"),
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
    frontLang: readString(card.front_lang, "card.front_lang"),
    backLang: readString(card.back_lang, "card.back_lang"),
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

export function parseImportLibraryCardsResult(value: unknown): ImportLibraryCardsResult {
  const result = readRecord(value, "cardImport");
  const importedCount = readInteger(result.imported_count, "cardImport.imported_count");
  const cards = result.cards;

  if (importedCount < 1 || importedCount > 500 || !Array.isArray(cards)) {
    return invalidLibraryResponse("cardImport");
  }

  const importedCards = cards.map((value, index) => {
    const path = `cardImport.cards[${index}]`;
    const card = readRecord(value, path);
    const position = readInteger(card.position, `${path}.position`);

    if (position < 1) {
      return invalidLibraryResponse(`${path}.position`);
    }

    return {
      uuid: readUuid(card.uuid, `${path}.uuid`),
      position,
    };
  });

  if (importedCards.length !== importedCount) {
    return invalidLibraryResponse("cardImport.cards");
  }

  return { importedCount, cards: importedCards };
}

function parseDeck(value: unknown, index: number): LibraryDeck {
  const path = `decks[${index}]`;
  const item = readRecord(value, path);
  const deckPath = `${path}.deck`;
  const viewerStatePath = `${path}.viewer_state`;
  const deck = readRecord(item.deck, deckPath);
  const viewerState = readRecord(item.viewer_state, viewerStatePath);
  const previewCards = item.preview_cards;
  const totalWordsCount = readInteger(deck.words_count, `${deckPath}.words_count`);
  const accuracy = readInteger(viewerState.accuracy, `${viewerStatePath}.accuracy`);

  if (!Array.isArray(previewCards)) {
    return invalidLibraryResponse(`${path}.preview_cards`);
  }

  if (totalWordsCount < 0) {
    return invalidLibraryResponse(`${deckPath}.words_count`);
  }
  if (accuracy < 0 || accuracy > 100) {
    return invalidLibraryResponse(`${viewerStatePath}.accuracy`);
  }

  return {
    uuid: readUuid(deck.uuid, `${deckPath}.uuid`),
    ownerUuid: readUuid(deck.owner_uuid, `${deckPath}.owner_uuid`),
    title: readString(deck.title, `${deckPath}.title`),
    description: readNullableString(deck.description, `${deckPath}.description`),
    totalWordsCount,
    accuracy,
    isFavourite: readBoolean(viewerState.is_favourite, `${viewerStatePath}.is_favourite`),
    updatedAt: readNullableDateTime(deck.updated_at, `${deckPath}.updated_at`),
    cards: previewCards.map((card, cardIndex) =>
      parsePreviewCard(card, `${path}.preview_cards[${cardIndex}]`),
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
