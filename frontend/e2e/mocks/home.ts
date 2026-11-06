import { buildEmptyHome, buildEmptyReviewSummary } from "../data/builders";
import type { ApiMockRouter } from "./api-router";

/**
 * Landing state after sign-in for a user without decks and activity: `GET /bff/home`
 * and `GET /bff/reviews/summary` that the "Review today" widget loads after it.
 */
export function mockEmptyHome(api: ApiMockRouter): void {
  api.on("GET", "/bff/home", async ({ route }) => {
    await route.fulfill({ json: buildEmptyHome() });
  });
  mockEmptyReviewSummary(api);
}

/** `GET /bff/reviews/summary` of a user who has nothing to review yet. */
export function mockEmptyReviewSummary(api: ApiMockRouter): void {
  api.on("GET", "/bff/reviews/summary", async ({ route }) => {
    await route.fulfill({ json: buildEmptyReviewSummary() });
  });
}
