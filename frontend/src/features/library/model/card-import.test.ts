import { describe, expect, it } from "vitest";
import { parseCardImportJson } from "./card-import";

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
    expect(parseCardImportJson('{"cards":[{"back_text":"hello"}]}')).toEqual({
      ok: false,
      issue: { code: "text", path: "cards[0].front_text", maxLength: 255 },
    });
  });
});
