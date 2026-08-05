import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthContextValue, AuthStatus } from "../../auth/model/auth-types";

const { useAuthMock } = vi.hoisted(() => ({ useAuthMock: vi.fn() }));

vi.mock("../../auth/hooks/useAuth", () => ({
  useAuth: useAuthMock,
}));

import { RouteGuard } from "./RouteGuard";

function setAuthStatus(status: AuthStatus): void {
  const initialize = vi.fn(async () => undefined);

  useAuthMock.mockReturnValue({
    status,
    user: null,
    error: status === "error" ? new Error("Session check failed") : null,
    isAuthenticated: status === "authorized",
    initialize,
    login: vi.fn(async () => undefined),
    logout: vi.fn(async () => undefined),
    refresh: vi.fn(async () => undefined),
    applyUserSettings: vi.fn(),
  } satisfies AuthContextValue);
}

function renderGuard(access: "public" | "protected" | "guest"): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <RouteGuard access={access}>
        <main>Содержимое страницы</main>
      </RouteGuard>
    </MemoryRouter>,
  );
}

describe("RouteGuard session states", () => {
  beforeEach(() => {
    useAuthMock.mockReset();
  });

  it("renders the page loader without visible session text while the session is loading", () => {
    setAuthStatus("loading");

    const markup = renderGuard("protected");

    expect(markup).toContain('role="status"');
    expect(markup).toContain('aria-label="Загрузка страницы"');
    expect(markup).toContain('class="page-loader__spinner"');
    expect(markup).not.toContain("Проверяем сессию");
  });

  it("renders a retry action for a completed session check error", () => {
    setAuthStatus("error");

    const markup = renderGuard("guest");

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Не удалось проверить сессию");
    expect(markup).toContain("Повторить");
    expect(markup).not.toContain("Содержимое страницы");
  });

  it("fails closed while an authorized session is being revalidated for a protected route", () => {
    setAuthStatus("authorized");

    const markup = renderGuard("protected");

    expect(markup).toContain('aria-label="Загрузка страницы"');
    expect(markup).not.toContain("Содержимое страницы");
  });

  it("renders the login route immediately for a known unauthorized session", () => {
    setAuthStatus("unauthorized");

    expect(renderGuard("guest")).toContain("Содержимое страницы");
  });

  it("does not block public routes on an auth error", () => {
    setAuthStatus("error");

    expect(renderGuard("public")).toContain("Содержимое страницы");
  });
});
