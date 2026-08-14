import { describe, expect, it } from "vitest";
import {
  getSafeReturnPath,
  hasSessionExpiredNotice,
  HOME_PATH,
  SESSION_EXPIRED_NOTICE,
  withoutSessionExpiredNotice,
} from "./navigation-state";

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

  it("recognizes only the explicit session-expired login notice", () => {
    expect(hasSessionExpiredNotice({ notice: SESSION_EXPIRED_NOTICE })).toBe(true);
    expect(hasSessionExpiredNotice({ notice: "server-error" })).toBe(false);
    expect(hasSessionExpiredNotice(null)).toBe(false);
  });

  it("removes a consumed session notice while preserving the return path", () => {
    expect(
      withoutSessionExpiredNotice({
        from: "/practice?deck=missing",
        notice: SESSION_EXPIRED_NOTICE,
      }),
    ).toEqual({ from: "/practice?deck=missing" });
    expect(withoutSessionExpiredNotice({ notice: SESSION_EXPIRED_NOTICE })).toBeNull();
    expect(withoutSessionExpiredNotice({ notice: "server-error" })).toEqual({
      notice: "server-error",
    });
  });
});
