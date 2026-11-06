import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { LocaleProvider } from "../../i18n";

vi.mock("../../auth/hooks/useAuth", () => ({
  useAuth: () => ({
    status: "authorized",
    user: {
      uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
      username: "alice",
      email: "alice@example.com",
      settings: {
        locale: "ru-RU",
        showPreviewsForLong: true,
        theme: "system",
        timezone: "Europe/Moscow",
      },
    },
    applyUserSettings: vi.fn(),
  }),
}));

const { detectBrowserTimezone } = vi.hoisted(() => ({
  detectBrowserTimezone: vi.fn<() => string | null>(() => "Asia/Tokyo"),
}));

vi.mock("../../features/settings/model/timezones", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../features/settings/model/timezones")>()),
  detectBrowserTimezone,
}));

import { SettingsPage } from "./SettingsPage";

describe("SettingsPage", () => {
  it("renders locale and theme controls from the authenticated user settings", () => {
    const markup = renderToStaticMarkup(<SettingsPage />);

    expect(markup).toContain("Настройки");
    expect(markup).not.toContain("alice@example.com");
    expect(markup).toContain('name="locale"');
    expect(markup).toMatch(/<option[^>]*value="ru-RU"[^>]*selected=""/);
    expect(markup).toContain('<option value="en-US">en (English)</option>');
    expect(markup).toContain('<option value="ru-RU" selected="">ru (Russian)</option>');
    expect(markup.indexOf("en (English)")).toBeLessThan(markup.indexOf("ru (Russian)"));
    expect(markup).toContain('name="theme"');
    expect(markup).toContain('value="light"');
    expect(markup).toContain('value="dark"');
    expect(markup).toMatch(/name="theme" checked="" value="system"/);
    expect(markup).toContain('data-active-theme="system"');
    expect(markup).toContain('name="show_previews_for_long"');
    expect(markup).toMatch(/name="show_previews_for_long"[^>]*checked=""/);
    expect(markup).toContain("Предпросмотр длинного текста");
    expect(markup).toContain("Показывать полный текст при наведении или фокусе");
    expect(markup).toContain("Включено");
    expect(markup).toContain("Сохранить");
    expect(markup).not.toContain("Привет");
    expect(markup).not.toContain("Настройте Etch");
    expect(markup).not.toContain("Выберите локаль");
  });

  it("renders the saved timezone with its offset, without a hint", () => {
    const markup = renderToStaticMarkup(<SettingsPage />);

    expect(markup).toContain("Часовой пояс");
    expect(markup).not.toContain("По нему считается");
    expect(markup).toMatch(/<select[^>]*name="timezone"/);
    expect(markup).not.toMatch(/<select[^>]*aria-describedby/);
    expect(markup).toMatch(
      /<option value="Europe\/Moscow" selected="">Europe\/Moscow \(UTC\+03:00\)</,
    );
  });

  it("orders timezones from the western offset to the eastern one", () => {
    const markup = renderToStaticMarkup(<SettingsPage />);

    const positions = ["America/New_York", "UTC", "Europe/Moscow", "Asia/Tokyo"].map((zone) =>
      markup.indexOf(`<option value="${zone}"`),
    );
    expect(positions.every((position) => position >= 0)).toBe(true);
    expect([...positions].sort((left, right) => left - right)).toEqual(positions);
  });

  it("offers the device timezone when it differs from the saved one", () => {
    const markup = renderToStaticMarkup(<SettingsPage />);

    expect(markup).toContain("Как на устройстве: Asia/Tokyo");
  });

  it("does not offer the device timezone when it is already saved", () => {
    detectBrowserTimezone.mockReturnValueOnce("Europe/Moscow");

    const markup = renderToStaticMarkup(<SettingsPage />);

    expect(markup).not.toContain("Как на устройстве");
  });

  it("renders settings controls in English", () => {
    const markup = renderToStaticMarkup(
      <LocaleProvider initialLocale="en-US">
        <SettingsPage />
      </LocaleProvider>,
    );

    expect(markup).toContain("Settings");
    expect(markup).toContain(">Language<");
    expect(markup).toContain("Appearance");
    expect(markup).toContain("Long text previews");
    expect(markup).toContain("Time zone");
    expect(markup).toContain("Show the full text on hover or focus");
    expect(markup).toContain("Save");
    expect(markup).not.toContain("Hello");
    expect(markup).not.toContain("Choose the locale");
  });
});
