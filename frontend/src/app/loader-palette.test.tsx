/// <reference types="node" />

import { runInNewContext } from "node:vm";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import indexHtml from "../../index.html?raw";
import { LocaleProvider } from "../i18n";
import { PageLoader } from "./PageLoader";

interface BootOptions {
  locale?: string | null;
  theme?: string | null;
  pathname?: string;
  prefersDark?: boolean;
  storageUnavailable?: boolean;
}

function runBootScripts({
  locale = null,
  theme = null,
  pathname = "/",
  prefersDark = false,
  storageUnavailable = false,
}: BootOptions = {}) {
  const documentElement = {
    lang: "ru-RU",
    dataset: { theme: "", bootPalette: "" },
    style: { colorScheme: "" },
  };
  const elements: Record<string, { setAttribute: ReturnType<typeof vi.fn> }> = {
    "theme-color": { setAttribute: vi.fn() },
    "meta-description": { setAttribute: vi.fn() },
    "boot-loader": { setAttribute: vi.fn() },
  };
  const context = {
    document: {
      documentElement,
      getElementById: (id: string) => elements[id] ?? null,
    },
    window: {
      localStorage: {
        getItem: (key: string) => {
          if (storageUnavailable) {
            throw new Error("Storage is unavailable");
          }
          return key === "etch.locale" ? locale : theme;
        },
      },
      location: { pathname },
      matchMedia: () => ({ matches: prefersDark }),
    },
  };
  const scripts = [...indexHtml.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(
    ([, source]) => source,
  );
  expect(scripts).not.toHaveLength(0);
  runInNewContext(scripts.join("\n"), context);

  return { documentElement, elements };
}

describe("HTML boot preferences", () => {
  it.each([
    ["light", true, "light"],
    ["dark", false, "dark"],
    ["system", true, "dark"],
    ["system", false, "light"],
  ])("resolves %s with system dark preference %s", (theme, prefersDark, resolvedTheme) => {
    const { documentElement } = runBootScripts({ theme, prefersDark });

    expect(documentElement.dataset.theme).toBe(resolvedTheme);
    expect(documentElement.style.colorScheme).toBe(resolvedTheme);
  });

  it.each(["/", "/library", "/library/cards", "/library/decks/archive", "/practice", "/settings"])(
    "selects the content loader palette for %s",
    (pathname) => {
      const { documentElement, elements } = runBootScripts({ pathname, theme: "light" });

      expect(documentElement.dataset.bootPalette).toBe("light");
      expect(elements["theme-color"].setAttribute).toHaveBeenCalledWith("content", "#f6f2eb");
    },
  );

  it("preserves the login palette before authentication", () => {
    const { documentElement, elements } = runBootScripts({ pathname: "/login", theme: "light" });

    expect(documentElement.dataset.bootPalette).toBe("dark");
    expect(elements["theme-color"].setAttribute).not.toHaveBeenCalled();
  });

  it("applies the dark browser theme color on content routes", () => {
    const { elements } = runBootScripts({ pathname: "/library", theme: "dark" });

    expect(elements["theme-color"].setAttribute).toHaveBeenCalledWith("content", "#171a18");
  });

  it("localizes the document, metadata and boot status from the saved locale", () => {
    const { documentElement, elements } = runBootScripts({ locale: "en-US" });

    expect(documentElement.lang).toBe("en-US");
    expect(elements["meta-description"].setAttribute).toHaveBeenCalledWith(
      "content",
      "Etch — a calm space for learning and remembering vocabulary.",
    );
    expect(elements["boot-loader"].setAttribute).toHaveBeenCalledWith("aria-label", "Loading page");
  });

  it("keeps Russian metadata and status for the Russian locale", () => {
    const { documentElement, elements } = runBootScripts({ locale: "ru-RU" });

    expect(documentElement.lang).toBe("ru-RU");
    expect(elements["meta-description"].setAttribute).not.toHaveBeenCalled();
    expect(elements["boot-loader"].setAttribute).not.toHaveBeenCalled();
  });

  it.each([
    { locale: null, theme: null },
    { locale: "de-DE", theme: "sepia" },
    { storageUnavailable: true },
  ])("falls back to Russian and the light theme for unavailable preferences: %o", (options) => {
    const { documentElement } = runBootScripts({ ...options, prefersDark: true });

    expect(documentElement.lang).toBe("ru-RU");
    expect(documentElement.dataset.theme).toBe("light");
    expect(documentElement.style.colorScheme).toBe("light");
  });
});

describe("PageLoader", () => {
  it.each([
    ["ru-RU", "Загрузка страницы"],
    ["en-US", "Loading page"],
  ] as const)("announces loading in %s and hides the decorative spinner", (locale, label) => {
    const markup = renderToStaticMarkup(
      <LocaleProvider initialLocale={locale}>
        <PageLoader />
      </LocaleProvider>,
    );

    expect(markup).toContain(`aria-label="${label}"`);
    expect(markup).toContain('role="status"');
    expect(markup).toMatch(/<span[^>]*aria-hidden="true"/);
  });
});
