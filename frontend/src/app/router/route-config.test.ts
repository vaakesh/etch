import { describe, expect, it } from "vitest";
import { appRoutes } from "./route-config";

describe("app route configuration", () => {
  it("registers /login as a guest-only route", () => {
    const loginRoute = appRoutes.find(({ path }) => path === "/login");

    expect(loginRoute).toBeDefined();
    expect(loginRoute?.access).toBe("guest");
    expect(loginRoute?.title).toBe("Вход — Etch");
    expect(loginRoute?.Component).toBeDefined();
  });

  it("registers the empty root route as protected", () => {
    const homeRoute = appRoutes.find(({ path }) => path === "/");

    expect(homeRoute).toBeDefined();
    expect(homeRoute?.access).toBe("protected");
    expect(homeRoute?.title).toBe("Главная — Etch");
    expect(homeRoute?.Component).toBeDefined();
  });

  it("registers /library as a protected route", () => {
    const libraryRoute = appRoutes.find(({ path }) => path === "/library");

    expect(libraryRoute).toBeDefined();
    expect(libraryRoute?.access).toBe("protected");
    expect(libraryRoute?.title).toBe("Библиотека — Etch");
    expect(libraryRoute?.Component).toBeDefined();
  });

  it("registers the deck editor as a protected library route", () => {
    const deckEditorRoute = appRoutes.find(({ path }) => path === "/library/:deck_uuid/edit");

    expect(deckEditorRoute).toBeDefined();
    expect(deckEditorRoute?.access).toBe("protected");
    expect(deckEditorRoute?.title).toBe("Редактор колоды — Etch");
    expect(deckEditorRoute?.Component).toBeDefined();
  });

  it("registers /practice as a protected route", () => {
    const practiceRoute = appRoutes.find(({ path }) => path === "/practice");

    expect(practiceRoute).toBeDefined();
    expect(practiceRoute?.access).toBe("protected");
    expect(practiceRoute?.title).toBe("Практика — Etch");
    expect(practiceRoute?.Component).toBeDefined();
  });

  it("registers the session history as a protected practice route", () => {
    const historyRoute = appRoutes.find(
      ({ path }) => path === "/practice/sessions/:session_uuid/history",
    );

    expect(historyRoute).toBeDefined();
    expect(historyRoute?.access).toBe("protected");
    expect(historyRoute?.title).toBe("История сессии — Etch");
    expect(historyRoute?.Component).toBeDefined();
  });

  it("renders unmatched routes as a public 404 page", () => {
    const fallbackRoute = appRoutes.find(({ path }) => path === "*");

    expect(fallbackRoute).toBeDefined();
    expect(fallbackRoute?.access).toBe("public");
    expect(fallbackRoute?.title).toBe("Страница не найдена — Etch");
    expect(fallbackRoute?.Component).toBeDefined();
  });
});
