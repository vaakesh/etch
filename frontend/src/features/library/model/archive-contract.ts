import { ApiError } from "../../../api";
import type { ArchiveCard, ArchivedDeck, ArchiveOffer, PreservedArchive } from "./archive-types";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function invalid(path: string): never {
  throw new ApiError({
    status: 0,
    code: "INVALID_ARCHIVE_RESPONSE",
    message: `The backend returned an unexpected archive value at ${path}.`,
  });
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return invalid(path);
  return value as Record<string, unknown>;
}

function string(value: unknown, path: string): string {
  if (typeof value !== "string") return invalid(path);
  return value;
}

function uuid(value: unknown, path: string): string {
  const result = string(value, path);
  if (!UUID_PATTERN.test(result)) return invalid(path);
  return result;
}

function nullableUuid(value: unknown, path: string): string | null {
  return value === null ? null : uuid(value, path);
}

function dateTime(value: unknown, path: string): string {
  const result = string(value, path);
  if (Number.isNaN(Date.parse(result))) return invalid(path);
  return result;
}

function nonNegativeInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) return invalid(path);
  return value;
}

function boolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") return invalid(path);
  return value;
}

export function parsePreservedArchive(value: unknown): PreservedArchive {
  const result = record(value, "preservedArchive");
  const alreadyPreserved = boolean(result.already_preserved, "preservedArchive.already_preserved");
  const copyDeleted = boolean(result.copy_deleted, "preservedArchive.copy_deleted");
  if (copyDeleted && !alreadyPreserved) return invalid("preservedArchive.copy_deleted");
  return {
    uuid: uuid(result.uuid, "preservedArchive.uuid"),
    alreadyPreserved,
    copyDeleted,
  };
}

export function parseArchiveOffers(value: unknown): ArchiveOffer[] {
  if (!Array.isArray(value)) return invalid("archives");
  return value.map((item: unknown, index: number) => {
    const path = `archives[${index}]`;
    const offer = record(item, path);
    return {
      uuid: uuid(offer.uuid, `${path}.uuid`),
      title: string(offer.title, `${path}.title`),
      expiresAt: dateTime(offer.expires_at, `${path}.expires_at`),
      preservedDeckUuid: nullableUuid(offer.preserved_deck_uuid, `${path}.preserved_deck_uuid`),
    };
  });
}

export function parseArchivedDeck(value: unknown): ArchivedDeck {
  const deck = record(value, "archive");
  const reason = string(deck.archive_reason, "archive.archive_reason");
  if (reason !== "deleted" && reason !== "owner_deleted" && reason !== "made_private") {
    return invalid("archive.archive_reason");
  }
  return {
    uuid: uuid(deck.uuid, "archive.uuid"),
    title: string(deck.title, "archive.title"),
    description: deck.description === null ? null : string(deck.description, "archive.description"),
    wordsCount: nonNegativeInteger(deck.words_count, "archive.words_count"),
    archivedAt: dateTime(deck.archived_at, "archive.archived_at"),
    expiresAt: dateTime(deck.expires_at, "archive.expires_at"),
    archiveReason: reason,
    sourceDeckUuidSnapshot: nullableUuid(
      deck.source_deck_uuid_snapshot,
      "archive.source_deck_uuid_snapshot",
    ),
    preservedDeckUuid: nullableUuid(deck.preserved_deck_uuid, "archive.preserved_deck_uuid"),
  };
}

export function parseArchiveCards(value: unknown, limit: number): ArchiveCard[] {
  if (!Array.isArray(value) || value.length > limit) return invalid("archiveCards");
  return value.map((item: unknown, index: number) => {
    const path = `archiveCards[${index}]`;
    const card = record(item, path);
    return {
      uuid: uuid(card.uuid, `${path}.uuid`),
      frontText: string(card.front_text, `${path}.front_text`),
      backText: string(card.back_text, `${path}.back_text`),
      frontLang: string(card.front_lang, `${path}.front_lang`),
      backLang: string(card.back_lang, `${path}.back_lang`),
      updatedAt: dateTime(card.updated_at, `${path}.updated_at`),
    };
  });
}
