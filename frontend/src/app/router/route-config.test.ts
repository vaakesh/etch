import { describe, expect, it } from "vitest";
import { appRoutes } from "./route-config";

describe("app route configuration", () => {
  it("registers /login as a guest-only route", () => {
    const loginRoute = appRoutes.find(({ path }) => path === "/login");

    expect(loginRoute).toBeDefined();
    expect(loginRoute?.access).toBe("guest");
    expect(loginRoute?.Component).toBeDefined();
  });

  it("registers the empty root route as protected", () => {
    const homeRoute = appRoutes.find(({ path }) => path === "/");

    expect(homeRoute).toBeDefined();
    expect(homeRoute?.access).toBe("protected");
    expect(homeRoute?.Component).toBeDefined();
  });

  it("renders unmatched routes as a public 404 page", () => {
    const fallbackRoute = appRoutes.find(({ path }) => path === "*");

    expect(fallbackRoute).toBeDefined();
    expect(fallbackRoute?.access).toBe("public");
    expect(fallbackRoute?.Component).toBeDefined();
  });
});
