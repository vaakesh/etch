import { describe, expect, it } from "vitest";
import { isApiError } from "../../../api";
import { parseHomeDashboard } from "./home-contract";

const VALID_RESPONSE = {
  decks: [
    {
      title: "Daily Words",
      description: null,
      deck_total_words_count: 48,
      user_accuracy: 75,
      updated_at: "2026-07-17T10:30:00Z",
    },
  ],
  progress: {
    user_words_explored: 67,
    user_weekly_accuracy: 55.5,
    user_current_streak: 6,
    user_total_study_time: 120,
  },
  user_weekly_activity: [55, 67, 32, 12, 0, 38, 100],
};

describe("parseHomeDashboard", () => {
  it("maps the backend snake-case contract into the home model", () => {
    expect(parseHomeDashboard(VALID_RESPONSE)).toEqual({
      decks: [
        {
          title: "Daily Words",
          description: null,
          totalWordsCount: 48,
          accuracy: 75,
          updatedAt: "2026-07-17T10:30:00Z",
        },
      ],
      progress: {
        wordsExplored: 67,
        weeklyAccuracy: 55.5,
        currentStreakDays: 6,
        totalStudyTimeSeconds: 120,
      },
      weeklyActivity: [55, 67, 32, 12, 0, 38, 100],
    });
  });

  it("rejects a response that does not match the required BFF fields", () => {
    try {
      parseHomeDashboard({ ...VALID_RESPONSE, user_weekly_activity: [20, null] });
      expect.fail("Expected parseHomeDashboard to throw.");
    } catch (error) {
      expect(isApiError(error)).toBe(true);
      if (isApiError(error)) {
        expect(error.code).toBe("INVALID_HOME_RESPONSE");
        expect(error.status).toBe(0);
      }
    }
  });
});
