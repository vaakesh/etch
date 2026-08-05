import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { LocaleProvider } from "../../i18n";
import { NotFoundPage } from "./NotFoundPage";

describe("NotFoundPage", () => {
  it("renders a 404 message and a link to the root route", () => {
    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );

    expect(markup).toContain("404");
    expect(markup).toContain("Страница не найдена");
    expect(markup).toContain('href="/"');
  });

  it("renders the not-found state in English", () => {
    const markup = renderToStaticMarkup(
      <LocaleProvider initialLocale="en-US">
        <MemoryRouter>
          <NotFoundPage />
        </MemoryRouter>
      </LocaleProvider>,
    );

    expect(markup).toContain("Page not found");
    expect(markup).toContain("Go home");
  });
});
