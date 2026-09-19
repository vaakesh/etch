import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { LocaleProvider, type AppLocale } from "../../i18n";

vi.mock("../../auth/hooks/useAuth", () => ({
  useAuth: () => ({
    logout: vi.fn(async () => undefined),
    user: { username: "alice" },
  }),
}));

import { AppShell } from "./AppShell";

const suspendedPage = new Promise<void>(() => undefined);

function SuspendedPage(): never {
  throw suspendedPage;
}

function renderShell(
  pathname:
    | "/"
    | "/library"
    | "/library/714d882d-726e-4dcb-9303-a8bf4638429c/edit"
    | "/decks/714d882d-726e-4dcb-9303-a8bf4638429c"
    | "/practice"
    | "/settings",
  suspendContent = false,
  locale: AppLocale = "ru-RU",
): string {
  const page = suspendContent ? <SuspendedPage /> : <main>Правая часть: {pathname}</main>;

  return renderToStaticMarkup(
    <LocaleProvider initialLocale={locale}>
      <MemoryRouter initialEntries={[pathname]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route element={page} path={pathname} />
          </Route>
        </Routes>
      </MemoryRouter>
    </LocaleProvider>,
  );
}

describe("AppShell", () => {
  it.each([
    ["/", "0", "Главная"],
    ["/library", "1", "Библиотека"],
    ["/library/714d882d-726e-4dcb-9303-a8bf4638429c/edit", "1", "Библиотека"],
    ["/decks/714d882d-726e-4dcb-9303-a8bf4638429c", "1", "Библиотека"],
    ["/practice", "3", "Практика"],
    ["/settings", "5", "Настройки"],
  ] as const)("selects the navigation row for %s", (pathname, activeIndex, activeLabel) => {
    const markup = renderShell(pathname);
    const activeLink = markup.match(/<a[^>]*aria-current="page"[^>]*>/)?.[0];

    expect(markup.match(/aria-label="Основная навигация"/g)).toHaveLength(1);
    expect(markup.match(/aria-current="page"/g)).toHaveLength(1);
    expect(markup).toContain(`data-active-index="${activeIndex}"`);
    expect(activeLink).toContain(`aria-label="${activeLabel}"`);
    expect(markup).toContain('href="/"');
    expect(markup).toContain('href="/library"');
    expect(markup).toContain('href="/practice"');
    expect(markup).toContain('href="/settings"');
    expect(markup).toContain('href="/users/alice"');
    expect(markup).toMatch(/<a[^>]*aria-label="На главную"[^>]*href="\/"[^>]*>.*Etch.*<\/a>/);
    expect(markup).toContain('aria-controls="app-sidebar"');
    expect(markup).toContain("Правая часть:");
  });

  it("keeps the menu visible while only the route content is suspended", () => {
    const markup = renderShell("/library", true);

    expect(markup).toContain("Etch");
    expect(markup).toContain('aria-label="Основная навигация"');
    expect(markup).toContain("page-loader--light");
    expect(markup).toContain("page-loader--contained");
  });

  it("renders navigation and controls in English", () => {
    const markup = renderShell("/settings", false, "en-US");
    const activeLink = markup.match(/<a[^>]*aria-current="page"[^>]*>/)?.[0];

    expect(markup).toContain('aria-label="Main navigation"');
    expect(activeLink).toContain('aria-label="Settings"');
    expect(markup).toContain('aria-label="Go to home"');
    expect(markup).toContain('title="This section is not available yet"');
    expect(markup).toContain('aria-label="Open my profile @alice"');
    expect(markup).toContain(">My profile</span>");
    expect(markup).toContain("<strong>@alice</strong>");
    expect(markup).toContain('aria-label="Sign out"');
    expect(markup).toContain(">Sign out</span>");
  });

  it("places a distinct current-user profile card before navigation and sign out at the end", () => {
    const markup = renderShell("/");
    const profileIndex = markup.indexOf('aria-label="Открыть мой профиль @alice"');
    const navigationIndex = markup.indexOf('aria-label="Основная навигация"');
    const logoutIndex = markup.indexOf('aria-label="Выйти"');

    expect(markup).toMatch(
      /<a[^>]*aria-label="Открыть мой профиль @alice"[^>]*href="\/users\/alice"[^>]*>/,
    );
    expect(markup).toContain(">Мой профиль</span>");
    expect(markup).toContain("<strong>@alice</strong>");
    expect(markup).toContain('aria-label="Выйти"');
    expect(markup).toContain(">Выйти</span>");
    expect(profileIndex).toBeGreaterThan(-1);
    expect(profileIndex).toBeLessThan(navigationIndex);
    expect(logoutIndex).toBeGreaterThan(navigationIndex);
  });
});
