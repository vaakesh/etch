import { describe, expect, it } from "vitest";
import { parseCurrentUser } from "./auth-contract";

describe("auth contract", () => {
  it("maps /users/me to the frontend user model", () => {
    expect(
      parseCurrentUser({
        uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
        username: "alice",
        email: "alice@example.com",
        created_at: "2026-07-31T10:15:00Z",
        updated_at: "2026-08-01T08:30:00Z",
        settings: { locale: "ru-RU", theme: "system", show_previews_for_long: true },
      }),
    ).toEqual({
      uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
      username: "alice",
      email: "alice@example.com",
      settings: { locale: "ru-RU", showPreviewsForLong: true, theme: "system" },
    });
  });

  it("keeps /users/me timestamps outside the narrower auth user model", () => {
    const user = parseCurrentUser({
      uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
      username: "alice",
      email: "alice@example.com",
      created_at: "2026-07-31T10:15:00Z",
      updated_at: "2026-08-01T08:30:00Z",
      settings: { locale: "en-US", theme: "dark", show_previews_for_long: false },
    });

    expect(user).not.toHaveProperty("created_at");
    expect(user).not.toHaveProperty("updated_at");
  });

  it("rejects an invalid /users/me response", () => {
    expect(() => parseCurrentUser({ uuid: "user-id", username: "alice" })).toThrowError(
      expect.objectContaining({ code: "INVALID_USER_RESPONSE" }),
    );
  });

  it("rejects /users/me when its required settings are invalid", () => {
    expect(() =>
      parseCurrentUser({
        uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
        username: "alice",
        email: "alice@example.com",
        settings: { locale: "fr-FR", theme: "light", show_previews_for_long: true },
      }),
    ).toThrowError(expect.objectContaining({ code: "INVALID_USER_RESPONSE" }));
  });
});
