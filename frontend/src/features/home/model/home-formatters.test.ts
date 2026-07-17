import { describe, expect, it } from "vitest";
import { clampPercent, formatStreak, formatStudyTime } from "./home-formatters";

describe("home dashboard formatters", () => {
  it("clamps backend percentages for safe visual rendering", () => {
    expect(clampPercent(-8)).toBe(0);
    expect(clampPercent(42.5)).toBe(42.5);
    expect(clampPercent(130)).toBe(100);
  });

  it("formats study time stored by the BFF in seconds", () => {
    expect(formatStudyTime(45)).toBe("45 сек");
    expect(formatStudyTime(120)).toBe("2 мин");
    expect(formatStudyTime(45_000)).toBe("12 ч 30 мин");
  });

  it("uses the correct Russian day form for a streak", () => {
    expect(formatStreak(1)).toBe("1 день");
    expect(formatStreak(3)).toBe("3 дня");
    expect(formatStreak(11)).toBe("11 дней");
  });
});
