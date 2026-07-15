import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const { loginMock } = vi.hoisted(() => ({ loginMock: vi.fn() }));

vi.mock("../../auth/hooks/useAuth", () => ({
  useAuth: () => ({ login: loginMock }),
}));

import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  it("renders a focused username and password login form", () => {
    const markup = renderToStaticMarkup(<LoginPage />);

    expect(markup).toContain("С возвращением");
    expect(markup).toContain("Имя пользователя");
    expect(markup).toContain('name="username"');
    expect(markup.match(/autocomplete="off"/gi)).toHaveLength(3);
    expect(markup).toContain('name="password"');
    expect(markup).toContain('type="password"');
    expect(markup.match(/readonly=""/gi)).toHaveLength(2);
    expect(markup).not.toMatch(/autocomplete="(?:username|current-password)"/i);
    expect(markup).not.toContain('type="email"');
  });
});
