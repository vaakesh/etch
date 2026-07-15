import { describe, expect, it } from "vitest";
import { getSafeReturnPath, HOME_PATH } from "./navigation-state";

describe("navigation state", () => {
  it("uses the root path as the authenticated fallback", () => {
    expect(HOME_PATH).toBe("/");
    expect(getSafeReturnPath(undefined, HOME_PATH)).toBe("/");
  });

  it("preserves a safe internal return path", () => {
    expect(getSafeReturnPath({ from: "/decks?page=2#recent" })).toBe("/decks?page=2#recent");
  });

  it.each([
    null,
    { from: 42 },
    { from: "https://example.com" },
    { from: "//example.com" },
    { from: "/login" },
  ])("rejects an unsafe return state", (state) => {
    expect(getSafeReturnPath(state)).toBe(HOME_PATH);
  });
});
