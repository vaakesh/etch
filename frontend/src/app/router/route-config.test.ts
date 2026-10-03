import { describe, expect, it } from "vitest";
import { matchRoutes } from "react-router-dom";
import { appRoutes } from "./route-config";

describe("app route configuration", () => {
  it.each(["/library/decks", "/library/cards"])(
    "registers %s as a protected library view",
    (path) => {
      const route = appRoutes.find((item) => item.path === path);
      expect(route?.access).toBe("protected");
      expect(route?.Component).toBeDefined();
      expect(
        matchRoutes(
          appRoutes.map(({ path }) => ({ path })),
          path,
        )?.at(-1)?.route.path,
      ).toBe(path);
    },
  );

  it("matches the archive route independently of deck details and editing", () => {
    const archive = appRoutes.find(({ path }) => path === "/library/decks/archive");
    expect(archive?.access).toBe("protected");
    const routes = appRoutes.map(({ path }) => ({ path }));
    for (const path of ["/library/decks/archive", "/library/decks/archive/"]) {
      expect(matchRoutes(routes, path)?.at(-1)?.route.path).toBe("/library/decks/archive");
    }
    expect(
      matchRoutes(routes, "/library/0199c27d-9a31-7e11-8f08-b193932384e5/edit")?.at(-1)?.route.path,
    ).toBe("/library/:deck_uuid/edit");
    expect(
      matchRoutes(routes, "/decks/0199c27d-9a31-7e11-8f08-b193932384e5")?.at(-1)?.route.path,
    ).toBe("/decks/:deck_uuid");
  });
  it("registers /login as a guest-only route", () => {
    const loginRoute = appRoutes.find(({ path }) => path === "/login");

    expect(loginRoute).toBeDefined();
    expect(loginRoute?.access).toBe("guest");
    expect(loginRoute?.title).toEqual({ "ru-RU": "Вход — Etch", "en-US": "Sign in — Etch" });
    expect(loginRoute?.Component).toBeDefined();
  });

  it("registers the empty root route as protected", () => {
    const homeRoute = appRoutes.find(({ path }) => path === "/");

    expect(homeRoute).toBeDefined();
    expect(homeRoute?.access).toBe("protected");
    expect(homeRoute?.title).toEqual({ "ru-RU": "Главная — Etch", "en-US": "Home — Etch" });
    expect(homeRoute?.Component).toBeDefined();
  });

  it("registers /library as a protected route", () => {
    const libraryRoute = appRoutes.find(({ path }) => path === "/library");

    expect(libraryRoute).toBeDefined();
    expect(libraryRoute?.access).toBe("protected");
    expect(libraryRoute?.title).toEqual({
      "ru-RU": "Библиотека — Etch",
      "en-US": "Library — Etch",
    });
    expect(libraryRoute?.Component).toBeDefined();
  });

  it("registers the deck editor as a protected library route", () => {
    const deckEditorRoute = appRoutes.find(({ path }) => path === "/library/:deck_uuid/edit");

    expect(deckEditorRoute).toBeDefined();
    expect(deckEditorRoute?.access).toBe("protected");
    expect(deckEditorRoute?.title).toEqual({
      "ru-RU": "Редактор колоды — Etch",
      "en-US": "Deck editor — Etch",
    });
    expect(deckEditorRoute?.Component).toBeDefined();
  });

  it("registers the deck details page as a protected route", () => {
    const deckDetailsRoute = appRoutes.find(({ path }) => path === "/decks/:deck_uuid");

    expect(deckDetailsRoute).toBeDefined();
    expect(deckDetailsRoute?.access).toBe("protected");
    expect(deckDetailsRoute?.title).toEqual({
      "ru-RU": "Колода — Etch",
      "en-US": "Deck — Etch",
    });
    expect(deckDetailsRoute?.Component).toBeDefined();
  });

  it("registers user profiles as a protected route", () => {
    const userProfileRoute = appRoutes.find(({ path }) => path === "/users/:username");

    expect(userProfileRoute).toBeDefined();
    expect(userProfileRoute?.access).toBe("protected");
    expect(userProfileRoute?.title).toEqual({
      "ru-RU": "Профиль — Etch",
      "en-US": "Profile — Etch",
    });
    expect(userProfileRoute?.Component).toBeDefined();
  });

  it("registers /practice as a protected route", () => {
    const practiceRoute = appRoutes.find(({ path }) => path === "/practice");

    expect(practiceRoute).toBeDefined();
    expect(practiceRoute?.access).toBe("protected");
    expect(practiceRoute?.title).toEqual({
      "ru-RU": "Практика — Etch",
      "en-US": "Practice — Etch",
    });
    expect(practiceRoute?.Component).toBeDefined();
  });

  it("registers the session history as a protected practice route", () => {
    const historyRoute = appRoutes.find(
      ({ path }) => path === "/practice/sessions/:session_uuid/history",
    );

    expect(historyRoute).toBeDefined();
    expect(historyRoute?.access).toBe("protected");
    expect(historyRoute?.title).toEqual({
      "ru-RU": "История сессии — Etch",
      "en-US": "Session history — Etch",
    });
    expect(historyRoute?.Component).toBeDefined();
  });

  it("registers /settings as a protected route", () => {
    const settingsRoute = appRoutes.find(({ path }) => path === "/settings");

    expect(settingsRoute).toBeDefined();
    expect(settingsRoute?.access).toBe("protected");
    expect(settingsRoute?.title).toEqual({
      "ru-RU": "Настройки — Etch",
      "en-US": "Settings — Etch",
    });
    expect(settingsRoute?.Component).toBeDefined();
  });

  it("renders unmatched routes as a public 404 page", () => {
    const fallbackRoute = appRoutes.find(({ path }) => path === "*");

    expect(fallbackRoute).toBeDefined();
    expect(fallbackRoute?.access).toBe("public");
    expect(fallbackRoute?.title).toEqual({
      "ru-RU": "Страница не найдена — Etch",
      "en-US": "Page not found — Etch",
    });
    expect(fallbackRoute?.Component).toBeDefined();
  });
});
