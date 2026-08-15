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
      settings: { locale: "ru-RU", showPreviewsForLong: true, theme: "system" },
    },
    applyUserSettings: vi.fn(),
  }),
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
    expect(markup).toContain("Show the full text on hover or focus");
    expect(markup).toContain("Save");
    expect(markup).not.toContain("Hello");
    expect(markup).not.toContain("Choose the locale");
  });
});
