import { describe, expect, it } from "vitest";
import { parseUserSettings } from "./settings-contract";

describe("settings contract", () => {
  it("maps the settings response to the frontend model", () => {
    expect(parseUserSettings({ locale: "en-US", theme: "dark" })).toEqual({
      locale: "en-US",
      theme: "dark",
    });
  });

  it.each([
    { locale: "de-DE", theme: "dark" },
    { locale: "ru-RU", theme: "sepia" },
    { theme: "light" },
  ])("rejects an unsupported settings response: %o", (payload) => {
    expect(() => parseUserSettings(payload)).toThrowError(
      expect.objectContaining({ code: "INVALID_SETTINGS_RESPONSE" }),
    );
  });
});
