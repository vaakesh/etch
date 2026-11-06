import { describe, expect, it } from "vitest";
import { formatNextReview } from "./review-formatters";

const NOW = new Date("2026-11-06T12:00:00Z");

describe("formatNextReview", () => {
  it("shows minutes for a review within the next hour", () => {
    expect(formatNextReview("2026-11-06T12:25:00Z", NOW, "ru-RU")).toBe("через 25 минут");
    expect(formatNextReview("2026-11-06T12:25:00Z", NOW, "en-US")).toBe("in 25 minutes");
  });

  it("shows hours for a review later within a day", () => {
    expect(formatNextReview("2026-11-06T15:10:00Z", NOW, "ru-RU")).toBe("через 3 часа");
  });

  it("does not show a past time for a review that is already due", () => {
    expect(formatNextReview("2026-11-06T11:00:00Z", NOW, "en-US")).toBe("in 1 minute");
  });

  it("shows the date and time for a review a day or more ahead", () => {
    const localDue = new Date(2026, 10, 9, 9, 5);

    expect(formatNextReview(localDue.toISOString(), NOW, "ru-RU")).toBe("9 нояб., 09:05");
  });

  it("returns null for an unparsable timestamp", () => {
    expect(formatNextReview("not-a-date", NOW, "ru-RU")).toBeNull();
  });
});
