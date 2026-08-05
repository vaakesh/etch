import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import indexHtml from "../../index.html?raw";
import { PageLoader } from "./PageLoader";

describe("page loader palette", () => {
  it("uses the dashboard palette for protected-route boot loading", () => {
    expect(indexHtml).toContain(':root[data-boot-palette="light"]');
    expect(indexHtml).toContain("--loader-background: #f6f2eb");
    expect(indexHtml).toContain("--loader-track: #e7dfd4");
    expect(indexHtml).toContain("--loader-accent: #4d9892");
    expect(indexHtml).toContain('window.location.pathname === "/library"');
    expect(indexHtml).toContain('window.location.pathname.startsWith("/library/")');
    expect(indexHtml).toContain('window.location.pathname === "/practice"');
    expect(indexHtml).toContain('window.location.pathname === "/settings"');
    expect(indexHtml).toContain('window.localStorage.getItem("etch.theme")');
    expect(indexHtml).toContain("document.documentElement.dataset.theme = resolvedTheme");
  });

  it("localizes boot metadata and the screen-reader label from stored preferences", () => {
    expect(indexHtml).toContain('window.localStorage.getItem("etch.locale")');
    expect(indexHtml).toContain("document.documentElement.lang = selectedLocale");
    expect(indexHtml).toContain("Etch — a calm space for learning and remembering vocabulary.");
    expect(indexHtml).toContain('setAttribute("aria-label", "Loading page")');
  });

  it("renders a contained light loader for route content", () => {
    const markup = renderToStaticMarkup(<PageLoader contained tone="light" />);

    expect(markup).toContain("page-loader--light");
    expect(markup).toContain("page-loader--contained");
  });
});
