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
};

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
