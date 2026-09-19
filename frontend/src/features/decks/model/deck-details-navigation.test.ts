import { describe, expect, it } from "vitest";
import {
  DECK_DETAILS_ROUTE_PATH,
  createDeckDetailsNavigationState,
  getDeckDetailsPath,
  getDeckDetailsProfilePath,
  getDeckDetailsReturnTarget,
} from "./deck-details-navigation";

describe("deck details navigation", () => {
  it("keeps the route dynamic and builds a separate path for each deck", () => {
    expect(DECK_DETAILS_ROUTE_PATH).toBe("/decks/:deck_uuid");
    expect(getDeckDetailsPath("714d882d-726e-4dcb-9303-a8bf4638429c")).toBe(
      "/decks/714d882d-726e-4dcb-9303-a8bf4638429c",
    );
    expect(getDeckDetailsPath("f9b7ced5-fbea-4741-82fd-33ea144dab7c")).toBe(
      "/decks/f9b7ced5-fbea-4741-82fd-33ea144dab7c",
    );
  });

  it("preserves every supported return target", () => {
    for (const target of ["catalog", "home", "library", "practice", "profile"] as const) {
      expect(getDeckDetailsReturnTarget(createDeckDetailsNavigationState(target))).toBe(target);
    }

    expect(getDeckDetailsReturnTarget({ deckDetailsReturnTarget: "/decks" })).toBeNull();
  });

  it("builds a safe profile return path from navigation state", () => {
    const state = createDeckDetailsNavigationState("profile", "deck owner");

    expect(getDeckDetailsProfilePath(state)).toBe("/users/deck%20owner");
    expect(getDeckDetailsProfilePath({ profileUsername: "" })).toBeNull();
    expect(getDeckDetailsProfilePath(null)).toBeNull();
  });
});
