import { describe, expect, it } from "vitest";
import { parseUserSettings } from "./settings-contract";

describe("settings contract", () => {
  it("maps the settings response to the frontend model", () => {
    expect(
      parseUserSettings({
        locale: "en-US",
        theme: "dark",
        show_previews_for_long: false,
        timezone: "Europe/Moscow",
      }),
    ).toEqual({
      locale: "en-US",
      showPreviewsForLong: false,
      theme: "dark",
      timezone: "Europe/Moscow",
    });
  });

  it.each([
    { locale: "de-DE", theme: "dark", show_previews_for_long: true, timezone: "UTC" },
    { locale: "ru-RU", theme: "sepia", show_previews_for_long: true, timezone: "UTC" },
    { locale: "ru-RU", theme: "light", timezone: "UTC" },
    { locale: "ru-RU", theme: "light", show_previews_for_long: "yes", timezone: "UTC" },
    { locale: "ru-RU", theme: "light", show_previews_for_long: true },
    { locale: "ru-RU", theme: "light", show_previews_for_long: true, timezone: "" },
    { locale: "ru-RU", theme: "light", show_previews_for_long: true, timezone: null },
  ])("rejects an unsupported settings response: %o", (payload) => {
    expect(() => parseUserSettings(payload)).toThrowError(
      expect.objectContaining({ code: "INVALID_SETTINGS_RESPONSE" }),
    );
  });
});
