import { describe, expect, it } from "vitest";
import { formatNextReviewIn } from "./practice-next-review";

const NOW = new Date("2026-11-06T09:00:00Z");

describe("formatNextReviewIn", () => {
  it.each([
    ["2026-11-06T09:10:00Z", "через 10 минут"],
    ["2026-11-06T09:00:20Z", "через 1 минуту"],
    ["2026-11-06T08:59:00Z", "через 1 минуту"],
    ["2026-11-06T12:00:00Z", "через 3 часа"],
    ["2026-11-07T09:00:00Z", "завтра"],
    ["2026-11-10T09:00:00Z", "через 4 дня"],
    ["2027-01-05T09:00:00Z", "через 2 месяца"],
    ["2028-11-05T09:00:00Z", "через 2 года"],
  ])("formats %s as “%s”", (nextReviewAt, expected) => {
    expect(formatNextReviewIn(nextReviewAt, NOW, "ru-RU")).toBe(expected);
  });

  it("uses the English locale", () => {
    expect(formatNextReviewIn("2026-11-10T09:00:00Z", NOW, "en-US")).toBe("in 4 days");
  });

  it("returns null for an unparsable date", () => {
    expect(formatNextReviewIn("not a date", NOW, "ru-RU")).toBeNull();
  });
});
