import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../../api";
import {
  USER_PROFILE_DECK_PAGE_SIZE,
  getUserProfile,
  getUserProfileDeckPage,
} from "./user-profile-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const USER_UUID = "d2f61c35-11d0-489e-837d-3845418ba39e";
const PROFILE = {
  uuid: USER_UUID,
  username: "deck owner",
  created_at: "2024-03-12T14:35:00Z",
  deck_count: 7,
  total_saves_count: 42,
};

describe("user profile API", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("loads a profile by its encoded username", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValue(PROFILE);

    await expect(getUserProfile("deck owner", controller.signal)).resolves.toMatchObject({
      uuid: USER_UUID,
      username: "deck owner",
      totalSavesCount: 42,
    });
    expect(apiFetch).toHaveBeenCalledWith("/users/profile/deck%20owner", {
      signal: controller.signal,
    });
  });

  it("loads the user's next cursor page with the backend limit", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValue({ items: [], next_cursor: null, has_more: false });

    await expect(
      getUserProfileDeckPage(USER_UUID, "next page", controller.signal),
    ).resolves.toEqual({ decks: [], nextCursor: null, hasMore: false });
    expect(USER_PROFILE_DECK_PAGE_SIZE).toBe(30);
    expect(apiFetch).toHaveBeenCalledWith(`/users/${USER_UUID}/decks`, {
      query: { limit: 30, cursor: "next page" },
      signal: controller.signal,
    });
  });
});
