import { buildEmptyHome } from "../data/builders";
import type { ApiMockRouter } from "./api-router";

/** `GET /bff/home` of a user without decks and activity: the landing state after sign-in. */
export function mockEmptyHome(api: ApiMockRouter): void {
  api.on("GET", "/bff/home", async ({ route }) => {
    await route.fulfill({ json: buildEmptyHome() });
  });
}
