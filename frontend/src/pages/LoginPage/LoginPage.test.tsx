import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { LocaleProvider, type AppLocale } from "../../i18n";

const { loginMock } = vi.hoisted(() => ({ loginMock: vi.fn() }));

vi.mock("../../auth/hooks/useAuth", () => ({
  useAuth: () => ({ login: loginMock }),
}));

import { LoginPage } from "./LoginPage";

function renderLogin(state?: unknown, locale: AppLocale = "ru-RU"): string {
  return renderToStaticMarkup(
    <LocaleProvider initialLocale={locale}>
      <MemoryRouter initialEntries={[{ pathname: "/login", state }]}>
        <LoginPage />
      </MemoryRouter>
    </LocaleProvider>,
  );
}

describe("LoginPage", () => {
  it("renders a focused username and password login form", () => {
    const markup = renderLogin();

    expect(markup).toContain("С возвращением");
    expect(markup).toContain("Имя пользователя");
    expect(markup.match(/aria-hidden="true">\*<\/span>/g)).toHaveLength(2);
    expect(markup).toContain('name="username"');
    expect(markup).toContain('minLength="3"');
    expect(markup).toContain('maxLength="18"');
    expect(markup.match(/autocomplete="off"/gi)).toHaveLength(3);
    expect(markup).toContain('name="password"');
    expect(markup).toContain('type="password"');
    expect(markup).toContain('minLength="8"');
    expect(markup).toContain('maxLength="128"');
    expect(markup.match(/pattern="\\S\+"/g)).toHaveLength(2);
    expect(markup.match(/readonly=""/gi)).toHaveLength(2);
    expect(markup).not.toMatch(/autocomplete="(?:username|current-password)"/i);
    expect(markup).not.toContain('type="email"');
  });

  it("explains why an expired session redirected the user to login", () => {
    const markup = renderLogin({ notice: "session-expired", from: "/practice?deck=missing" });

    expect(markup).toContain("Сессия истекла. Войдите снова.");
    expect(markup).toContain('role="status"');
  });

  it("renders the complete form in English", () => {
    const markup = renderLogin(undefined, "en-US");

    expect(markup).toContain("Welcome back");
    expect(markup).toContain("Username");
    expect(markup).toContain("Password");
    expect(markup).toContain("Sign in");
  });
});
