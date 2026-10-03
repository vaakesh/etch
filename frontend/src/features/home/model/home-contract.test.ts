import { describe, expect, it } from "vitest";
import { isApiError } from "../../../api";
import { parseHomeDashboard } from "./home-contract";

const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const OWNER_UUID = "d2f61c35-11d0-489e-837d-3845418ba39e";

const VALID_RESPONSE = {
  decks: [
    {
      uuid: DECK_UUID,
      owner_uuid: OWNER_UUID,
      title: "Daily Words",
      description: null,
      words_count: 48,
      user_accuracy: 75,
      updated_at: "2026-07-17T10:30:00Z",
    },
  ],
  progress: {
    user_words_explored: 67,
    user_weekly_accuracy: 55,
    user_current_streak: 6,
    user_total_study_time: 120,
  },
  user_weekly_activity: [
    { date: "2026-07-12", value: 55 },
    { date: "2026-07-13", value: 67 },
    { date: "2026-07-14", value: 32 },
    { date: "2026-07-15", value: 12 },
    { date: "2026-07-16", value: 0 },
    { date: "2026-07-17", value: 38 },
    { date: "2026-07-18", value: 100 },
  ],
};

describe("parseHomeDashboard", () => {
  it("maps the backend snake-case contract into the home model", () => {
    expect(parseHomeDashboard(VALID_RESPONSE)).toEqual({
      decks: [
        {
          uuid: DECK_UUID,
          ownerUuid: OWNER_UUID,
          title: "Daily Words",
          description: null,
          totalWordsCount: 48,
          accuracy: 75,
          updatedAt: "2026-07-17T10:30:00Z",
        },
      ],
      progress: {
        wordsExplored: 67,
        weeklyAccuracy: 55,
        currentStreakDays: 6,
        totalStudyTimeSeconds: 120,
      },
      weeklyActivity: VALID_RESPONSE.user_weekly_activity,
    });
  });

  it("accepts daily counts above 100", () => {
    expect(
      parseHomeDashboard({
        ...VALID_RESPONSE,
        user_weekly_activity: [{ date: "2026-07-18", value: 250 }],
      }).weeklyActivity,
    ).toEqual([{ date: "2026-07-18", value: 250 }]);
  });

  it("rejects a response that does not match the required BFF fields", () => {
    try {
      parseHomeDashboard({
        ...VALID_RESPONSE,
        user_weekly_activity: [{ date: "2026-07-18", value: null }],
      });
      expect.fail("Expected parseHomeDashboard to throw.");
    } catch (error) {
      expect(isApiError(error)).toBe(true);
      if (isApiError(error)) {
        expect(error.code).toBe("INVALID_HOME_RESPONSE");
        expect(error.status).toBe(0);
      }
    }
  });

  it("rejects invalid calendar dates and activity counts outside the contract range", () => {
    expect(() =>
      parseHomeDashboard({
        ...VALID_RESPONSE,
        user_weekly_activity: [{ date: "2026-02-30", value: 50 }],
      }),
    ).toThrow();

    expect(() =>
      parseHomeDashboard({
        ...VALID_RESPONSE,
        user_weekly_activity: [{ date: "2026-07-18", value: -1 }],
      }),
    ).toThrow();

    expect(() =>
      parseHomeDashboard({
        ...VALID_RESPONSE,
        progress: { ...VALID_RESPONSE.progress, user_weekly_accuracy: 55.5 },
      }),
    ).toThrow();
  });
});
