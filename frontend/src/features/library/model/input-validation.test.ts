import { describe, expect, it } from "vitest";
import { isValidCardLanguage, isValidDeckTitle } from "./input-validation";

describe("backend input constraints", () => {
  it.each(["ru", "ENG", " en "])("accepts language %s", (value) => {
    expect(isValidCardLanguage(value)).toBe(true);
  });
  it.each(["рф", "e1", "e-", "e", "engl", "e n"])("rejects language %s", (value) => {
    expect(isValidCardLanguage(value)).toBe(false);
  });
  it.each(["\t", "\n", "\r", "\v", "\f", "\u0085", "\u2028", "\u2029"])(
    "rejects separator %j inside deck titles",
    (separator) => {
      expect(isValidDeckTitle(`Daily${separator}Words`)).toBe(false);
    },
  );
  it("validates the trimmed title and preserves Unicode", () => {
    expect(isValidDeckTitle("  Моя колода  ")).toBe(true);
    expect(isValidDeckTitle("ab")).toBe(false);
    expect(isValidDeckTitle("a".repeat(50))).toBe(true);
    expect(isValidDeckTitle("a".repeat(51))).toBe(false);
  });
});
