import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../../api";
import { getHomeDashboard } from "./home-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const RESPONSE = {
  decks: [],
  progress: {
    user_words_explored: 67,
    user_weekly_accuracy: 55,
    user_current_streak: 6,
    user_total_study_time: 120,
  },
  user_weekly_activity: [55, 67, 32, 12, 0, 38, 100],
};

describe("getHomeDashboard", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("loads the exact authenticated BFF route with the caller signal", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValue(RESPONSE);

    await expect(getHomeDashboard(controller.signal)).resolves.toMatchObject({
      decks: [],
      weeklyActivity: RESPONSE.user_weekly_activity,
    });

    expect(apiFetch).toHaveBeenCalledOnce();
    expect(apiFetch).toHaveBeenCalledWith("/bff/home", { signal: controller.signal });
  });
});
