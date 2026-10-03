import { MAX_DECK_SIZE, fitsIntoDeck, getDeckFreeSlots } from "./deck-capacity";
import { isValidCardLanguage } from "./input-validation";
import type { ImportLibraryCardsInput } from "./library-types";

const MAX_CARDS = 500;
const MAX_CARD_TEXT_LENGTH = 255;

export type CardImportIssue =
  | { code: "empty" }
  | { code: "json-syntax"; character: string | null; position: number }
  | { code: "root" }
  | { code: "cards-array" }
  | { code: "cards-empty" }
  | { code: "cards-limit"; limit: number }
  | { code: "deck-capacity"; limit: number; freeSlots: number }
  | { code: "card-object"; path: string }
  | { code: "text"; path: string; maxLength: number }
  | { code: "language"; path: string };

/** Импорт не поместится в колоду — backend ответил бы 409, проверяем заранее. */
export function checkDeckCapacity(
  deckWordsCount: number,
  importedCardsCount: number,
): CardImportIssue | null {
  if (fitsIntoDeck(deckWordsCount, importedCardsCount)) {
    return null;
  }

  return {
    code: "deck-capacity",
    limit: MAX_DECK_SIZE,
    freeSlots: getDeckFreeSlots(deckWordsCount),
  };
}

export type CardImportParseResult =
  { ok: true; value: ImportLibraryCardsInput } | { ok: false; issue: CardImportIssue };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getSyntaxPosition(error: unknown, source: string): number {
  const message = error instanceof Error ? error.message : "";
  const positionMatch = /position\s+(\d+)/i.exec(message);

  if (positionMatch !== null) {
    return Math.min(Number(positionMatch[1]), source.length);
  }

  const lineColumnMatch = /line\s+(\d+)\s+column\s+(\d+)/i.exec(message);
  if (lineColumnMatch !== null) {
    const targetLine = Number(lineColumnMatch[1]);
    const targetColumn = Number(lineColumnMatch[2]);
    const lines = source.split("\n");
    let position = 0;

    for (let index = 0; index < targetLine - 1 && index < lines.length; index += 1) {
      position += lines[index].length + 1;
    }

    return Math.min(position + Math.max(0, targetColumn - 1), source.length);
  }

  const unexpectedTokenMatch = /Unexpected token '([^']+)'/i.exec(message);
  if (unexpectedTokenMatch !== null) {
    const tokenPosition = source.indexOf(unexpectedTokenMatch[1]);
    if (tokenPosition >= 0) {
      return tokenPosition;
    }
  }

  return source.length;
}

function syntaxIssue(error: unknown, source: string): CardImportIssue {
  const position = getSyntaxPosition(error, source);

  return {
    code: "json-syntax",
    character: position < source.length ? source[position] : null,
    position: position + 1,
  };
}

function readText(
  value: unknown,
  path: string,
): { ok: true; value: string } | { ok: false; issue: CardImportIssue } {
  if (
    typeof value !== "string" ||
    value.trim().length === 0 ||
    [...value.trim()].length > MAX_CARD_TEXT_LENGTH
  ) {
    return { ok: false, issue: { code: "text", path, maxLength: MAX_CARD_TEXT_LENGTH } };
  }

  return { ok: true, value };
}

function readLanguage(
  value: unknown,
  path: string,
  defaultValue: string,
): { ok: true; value: string } | { ok: false; issue: CardImportIssue } {
  if (value === undefined) {
    return { ok: true, value: defaultValue };
  }

  if (typeof value !== "string" || !isValidCardLanguage(value)) {
    return { ok: false, issue: { code: "language", path } };
  }

  return { ok: true, value };
}

export function parseCardImportJson(source: string): CardImportParseResult {
  if (source.trim().length === 0) {
    return { ok: false, issue: { code: "empty" } };
  }

  let payload: unknown;
  try {
    payload = JSON.parse(source) as unknown;
  } catch (error: unknown) {
    return { ok: false, issue: syntaxIssue(error, source) };
  }

  if (!isRecord(payload)) {
    return { ok: false, issue: { code: "root" } };
  }
  if (!Array.isArray(payload.cards)) {
    return { ok: false, issue: { code: "cards-array" } };
  }
  if (payload.cards.length === 0) {
    return { ok: false, issue: { code: "cards-empty" } };
  }
  if (payload.cards.length > MAX_CARDS) {
    return { ok: false, issue: { code: "cards-limit", limit: MAX_CARDS } };
  }

  const cards: ImportLibraryCardsInput["cards"][number][] = [];

  for (const [index, value] of payload.cards.entries()) {
    const cardPath = `cards[${index}]`;
    if (!isRecord(value)) {
      return { ok: false, issue: { code: "card-object", path: cardPath } };
    }

    const frontText = readText(value.front_text, `${cardPath}.front_text`);
    if (!frontText.ok) {
      return frontText;
    }
    const backText = readText(value.back_text, `${cardPath}.back_text`);
    if (!backText.ok) {
      return backText;
    }
    const frontLang = readLanguage(value.front_lang, `${cardPath}.front_lang`, "ru");
    if (!frontLang.ok) {
      return frontLang;
    }
    const backLang = readLanguage(value.back_lang, `${cardPath}.back_lang`, "en");
    if (!backLang.ok) {
      return backLang;
    }

    cards.push({
      frontText: frontText.value,
      backText: backText.value,
      frontLang: frontLang.value,
      backLang: backLang.value,
    });
  }

  return { ok: true, value: { cards } };
}
