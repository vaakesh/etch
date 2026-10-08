import { describe, expect, it } from "vitest";
import { authReducer, initialAuthState } from "./auth-reducer";

const authorizedState = {
  status: "authorized" as const,
  user: {
    uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
    username: "alice",
    email: "alice@example.com",
    settings: {
      locale: "ru-RU" as const,
      showPreviewsForLong: true,
      theme: "light" as const,
    },
  },
  error: null,
  sessionExpired: false,
};

describe("auth reducer session end", () => {
  it("marks the session as expired only when the action says so", () => {
    expect(authReducer(authorizedState, { type: "unauthorized", expired: true })).toEqual({
      status: "unauthorized",
      user: null,
      error: null,
      sessionExpired: true,
    });
    expect(authReducer(authorizedState, { type: "unauthorized" }).sessionExpired).toBe(false);
  });

  it("clears the expiry mark when a new session check or session starts", () => {
    const expiredState = authReducer(authorizedState, { type: "unauthorized", expired: true });

    expect(authReducer(expiredState, { type: "loading" }).sessionExpired).toBe(false);
    expect(
      authReducer(expiredState, { type: "authorized", user: authorizedState.user }).sessionExpired,
    ).toBe(false);
  });
});

describe("auth reducer settings", () => {
  it("updates settings without replacing the authenticated identity", () => {
    expect(
      authReducer(authorizedState, {
        type: "settings-updated",
        settings: { locale: "en-US", showPreviewsForLong: false, theme: "system" },
      }),
    ).toEqual({
      ...authorizedState,
      user: {
        ...authorizedState.user,
        settings: { locale: "en-US", showPreviewsForLong: false, theme: "system" },
      },
    });
  });

  it("ignores local settings updates without an authenticated user", () => {
    expect(
      authReducer(initialAuthState, {
        type: "settings-updated",
        settings: { locale: "en-US", showPreviewsForLong: false, theme: "dark" },
      }),
    ).toBe(initialAuthState);
  });
});
