import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppShell } from "./AppShell";

const suspendedPage = new Promise<void>(() => undefined);

function SuspendedPage(): never {
  throw suspendedPage;
}

function renderShell(
  pathname: "/" | "/library" | "/library/714d882d-726e-4dcb-9303-a8bf4638429c/edit" | "/practice",
  suspendContent = false,
): string {
  const page = suspendContent ? <SuspendedPage /> : <main>Правая часть: {pathname}</main>;

  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[pathname]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route element={page} path={pathname} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("AppShell", () => {
  it.each([
    ["/", "0", "Главная"],
    ["/library", "1", "Библиотека"],
    ["/library/714d882d-726e-4dcb-9303-a8bf4638429c/edit", "1", "Библиотека"],
    ["/practice", "3", "Практика"],
  ] as const)("selects the navigation row for %s", (pathname, activeIndex, activeLabel) => {
    const markup = renderShell(pathname);

    expect(markup.match(/aria-label="Основная навигация"/g)).toHaveLength(1);
    expect(markup.match(/aria-current="page"/g)).toHaveLength(1);
    expect(markup).toContain(`data-active-index="${activeIndex}"`);
    expect(markup).toContain(`aria-label="${activeLabel}" aria-current="page"`);
    expect(markup).toContain('href="/"');
    expect(markup).toContain('href="/library"');
    expect(markup).toContain('href="/practice"');
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
});
