import { buildEmptyCursorPage, buildEmptyUserProfile } from "../data/builders";
import type { CurrentUserResponse } from "../data/builders";
import type { ApiMockRouter } from "./api-router";

/** Own profile without decks: `GET /users/profile/{username}` and `GET /users/{uuid}/decks`. */
export function mockEmptyOwnProfile(api: ApiMockRouter, user: CurrentUserResponse): void {
  api.on("GET", `/users/profile/${user.username}`, async ({ route }) => {
    await route.fulfill({ json: buildEmptyUserProfile(user) });
  });
  api.on("GET", `/users/${user.uuid}/decks`, async ({ route }) => {
    await route.fulfill({ json: buildEmptyCursorPage() });
  });
}
