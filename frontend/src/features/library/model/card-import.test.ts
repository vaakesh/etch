import { describe, expect, it } from "vitest";
import { checkDeckCapacity, parseCardImportJson } from "./card-import";
import { MAX_DECK_SIZE } from "./deck-capacity";

describe("parseCardImportJson", () => {
  it("maps the backend JSON shape and applies backend language defaults", () => {
    expect(
      parseCardImportJson(
        JSON.stringify({
          cards: [
            { front_text: "привет", back_text: "hello" },
            {
              front_text: "пока",
              back_text: "goodbye",
              front_lang: "ru",
              back_lang: "en",
            },
          ],
        }),
      ),
    ).toEqual({
      ok: true,
      value: {
        cards: [
          { frontText: "привет", backText: "hello", frontLang: "ru", backLang: "en" },
          { frontText: "пока", backText: "goodbye", frontLang: "ru", backLang: "en" },
        ],
      },
    });
  });

  it.each(["рф", "e1", "e-"])("rejects invalid language %s before import", (language) => {
    expect(
      parseCardImportJson(
        JSON.stringify({
          cards: [
            {
              front_text: "Привет",
              back_text: "Hello",
              front_lang: language,
            },
          ],
        }),
      ),
    ).toEqual({ ok: false, issue: { code: "language", path: "cards[0].front_lang" } });
  });

  it("reports a one-based syntax position and offending character", () => {
    const result = parseCardImportJson('{"cards":[,]}');

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.issue).toMatchObject({
        code: "json-syntax",
        character: ",",
        position: 11,
      });
    }
  });

  it("validates the card count and required backend fields", () => {
    expect(parseCardImportJson('{"cards":[]}')).toEqual({
      ok: false,
      issue: { code: "cards-empty" },
    });
    expect(
      parseCardImportJson(JSON.stringify({ cards: Array.from({ length: 501 }, () => ({})) })),
    ).toEqual({ ok: false, issue: { code: "cards-limit", limit: 500 } });
    for (const field of ["front_text", "back_text"]) {
      for (const character of ["a", "😀"]) {
        const card = { front_text: "привет", back_text: "hello" };
        expect(
          parseCardImportJson(
            JSON.stringify({ cards: [{ ...card, [field]: `  ${character.repeat(255)}  ` }] }),
          ),
        ).toMatchObject({ ok: true });
        expect(
          parseCardImportJson(
            JSON.stringify({ cards: [{ ...card, [field]: character.repeat(256) }] }),
          ),
        ).toEqual({
          ok: false,
          issue: { code: "text", path: `cards[0].${field}`, maxLength: 255 },
        });
      }
    }
    expect(parseCardImportJson('{"cards":[{"back_text":"hello"}]}')).toEqual({
      ok: false,
      issue: { code: "text", path: "cards[0].front_text", maxLength: 255 },
    });
  });
});

describe("checkDeckCapacity", () => {
  it("accepts an import that still fits into the deck limit", () => {
    expect(checkDeckCapacity(0, 500)).toBeNull();
    expect(checkDeckCapacity(4500, 500)).toBeNull();
    expect(checkDeckCapacity(MAX_DECK_SIZE, 0)).toBeNull();
  });

  it("reports the remaining slots when the import does not fit", () => {
    expect(checkDeckCapacity(4800, 300)).toEqual({
      code: "deck-capacity",
      limit: MAX_DECK_SIZE,
      freeSlots: 200,
    });
    expect(checkDeckCapacity(MAX_DECK_SIZE, 1)).toEqual({
      code: "deck-capacity",
      limit: MAX_DECK_SIZE,
      freeSlots: 0,
    });
  });
});
