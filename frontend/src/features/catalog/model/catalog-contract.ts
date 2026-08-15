import { ApiError } from "../../../api";
import type {
  CatalogDeck,
  CatalogDeckPreview,
  CatalogPreviewCard,
  CatalogPreviewCardPage,
} from "./catalog-types";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function invalidCatalogResponse(path: string): never {
  throw new ApiError({
    status: 0,
    code: "INVALID_CATALOG_RESPONSE",
    message: `The backend returned an unexpected catalog value at ${path}.`,
  });
}

function readRecord(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return invalidCatalogResponse(path);
  }

  return value as Record<string, unknown>;
}

function readString(value: unknown, path: string): string {
  if (typeof value !== "string") {
    return invalidCatalogResponse(path);
  }

  return value;
}

function readUuid(value: unknown, path: string): string {
  const uuid = readString(value, path);
  if (!UUID_PATTERN.test(uuid)) {
    return invalidCatalogResponse(path);
  }

  return uuid;
}

function readNullableString(value: unknown, path: string): string | null {
  return value === null ? null : readString(value, path);
}

function readNonNegativeInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    return invalidCatalogResponse(path);
  }

  return value;
}

function readBoolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") {
    return invalidCatalogResponse(path);
  }

  return value;
}

function readNullableDateTime(value: unknown, path: string): string | null {
  const dateTime = readNullableString(value, path);
  if (dateTime !== null && Number.isNaN(Date.parse(dateTime))) {
    return invalidCatalogResponse(path);
  }

  return dateTime;
}

function readDateTime(value: unknown, path: string): string {
  const dateTime = readString(value, path);
  if (Number.isNaN(Date.parse(dateTime))) {
    return invalidCatalogResponse(path);
  }

  return dateTime;
}

function readViewerIsSaved(value: unknown, path: string): boolean {
  if (value === null) {
    return false;
  }

  const viewerState = readRecord(value, path);
  return readBoolean(viewerState.is_saved, `${path}.is_saved`);
}

function parseCatalogDeck(value: unknown, index: number): CatalogDeck {
  const itemPath = `catalog[${index}]`;
  const item = readRecord(value, itemPath);
  const deckPath = `${itemPath}.deck`;
  const deck = readRecord(item.deck, deckPath);

  return {
    uuid: readUuid(deck.uuid, `${deckPath}.uuid`),
    ownerUuid: readUuid(deck.owner_uuid, `${deckPath}.owner_uuid`),
    title: readString(deck.title, `${deckPath}.title`),
    description: readNullableString(deck.description, `${deckPath}.description`),
    totalWordsCount: readNonNegativeInteger(deck.words_count, `${deckPath}.words_count`),
    savesCount: readNonNegativeInteger(deck.saves_count, `${deckPath}.saves_count`),
    isSaved: readViewerIsSaved(item.viewer_state, `${itemPath}.viewer_state`),
    isPublic: readBoolean(deck.is_public, `${deckPath}.is_public`),
    updatedAt: readNullableDateTime(deck.updated_at, `${deckPath}.updated_at`),
  };
}

export function parseCatalogDecks(value: unknown): readonly CatalogDeck[] {
  if (!Array.isArray(value)) {
    return invalidCatalogResponse("catalog");
  }

  return value.map(parseCatalogDeck);
}

export function parseCatalogDeckPreview(value: unknown): CatalogDeckPreview {
  const deck = readRecord(value, "deck");

  return {
    uuid: readUuid(deck.uuid, "deck.uuid"),
    ownerUuid: readUuid(deck.owner_uuid, "deck.owner_uuid"),
    title: readString(deck.title, "deck.title"),
    description: readNullableString(deck.description, "deck.description"),
    totalWordsCount: readNonNegativeInteger(deck.words_count, "deck.words_count"),
    savesCount: readNonNegativeInteger(deck.saves_count, "deck.saves_count"),
    isPublic: readBoolean(deck.is_public, "deck.is_public"),
    updatedAt: readNullableDateTime(deck.updated_at, "deck.updated_at"),
  };
}

function parseCatalogPreviewCard(value: unknown, index: number): CatalogPreviewCard {
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

export function parseCatalogPreviewCardPage(
  value: unknown,
  offset: number,
  limit: number,
): CatalogPreviewCardPage {
  if (!Array.isArray(value) || value.length > limit) {
    return invalidCatalogResponse("deckCards");
  }

  const cards = value.map(parseCatalogPreviewCard);

  return {
    cards,
    nextOffset: offset + cards.length,
    hasMore: cards.length === limit,
  };
}
