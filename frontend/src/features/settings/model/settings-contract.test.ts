import { describe, expect, it } from "vitest";
import { parseUserSettings } from "./settings-contract";

describe("settings contract", () => {
  it("maps the settings response to the frontend model", () => {
    expect(
      parseUserSettings({
        locale: "en-US",
        theme: "dark",
        show_previews_for_long: false,
      }),
    ).toEqual({
      locale: "en-US",
      showPreviewsForLong: false,
      theme: "dark",
    });
  });

  it.each([
    { locale: "de-DE", theme: "dark", show_previews_for_long: true },
    { locale: "ru-RU", theme: "sepia", show_previews_for_long: true },
    { locale: "ru-RU", theme: "light" },
    { locale: "ru-RU", theme: "light", show_previews_for_long: "yes" },
  ])("rejects an unsupported settings response: %o", (payload) => {
    expect(() => parseUserSettings(payload)).toThrowError(
      expect.objectContaining({ code: "INVALID_SETTINGS_RESPONSE" }),
    );
  });
});
