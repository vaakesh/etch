import { afterEach, describe, expect, it, vi } from "vitest";
import { detectBrowserTimezone, formatTimezoneOffset, getTimezoneOptions } from "./timezones";

afterEach(() => {
  vi.restoreAllMocks();
});

function mockResolvedTimezone(timeZone: string): void {
  vi.spyOn(Intl.DateTimeFormat.prototype, "resolvedOptions").mockReturnValue({
    ...new Intl.DateTimeFormat("en-US", { timeZone: "UTC" }).resolvedOptions(),
    timeZone,
  });
}

describe("detectBrowserTimezone", () => {
  it("returns the IANA zone the browser reports", () => {
    mockResolvedTimezone("Asia/Tokyo");

    expect(detectBrowserTimezone()).toBe("Asia/Tokyo");
  });

  it("returns null when the browser reports no zone", () => {
    mockResolvedTimezone("");

    expect(detectBrowserTimezone()).toBeNull();
  });

  it("returns null when Intl throws", () => {
    vi.spyOn(Intl.DateTimeFormat.prototype, "resolvedOptions").mockImplementation(() => {
      throw new RangeError("unsupported");
    });

    expect(detectBrowserTimezone()).toBeNull();
  });
});

describe("getTimezoneOptions", () => {
  const winter = new Date("2026-01-15T12:00:00Z");
  const summer = new Date("2026-07-15T12:00:00Z");

  it("orders zones from the western offset to the eastern one, UTC first among equals", () => {
    vi.spyOn(Intl, "supportedValuesOf").mockReturnValue([
      "Pacific/Kiritimati",
      "Europe/Moscow",
      "Africa/Abidjan",
      "Etc/GMT+12",
      "Asia/Kolkata",
      "America/New_York",
      "Europe/London",
    ]);

    expect(getTimezoneOptions("UTC", winter)).toEqual([
      { value: "Etc/GMT+12", offset: "UTC-12:00" },
      { value: "America/New_York", offset: "UTC-05:00" },
      { value: "UTC", offset: "UTC+00:00" },
      { value: "Africa/Abidjan", offset: "UTC+00:00" },
      { value: "Europe/London", offset: "UTC+00:00" },
      { value: "Europe/Moscow", offset: "UTC+03:00" },
      { value: "Asia/Kolkata", offset: "UTC+05:30" },
      { value: "Pacific/Kiritimati", offset: "UTC+14:00" },
    ]);
  });

  it("sorts by the offset at the given moment, with daylight saving time", () => {
    vi.spyOn(Intl, "supportedValuesOf").mockReturnValue(["Europe/London", "Africa/Abidjan"]);

    expect(getTimezoneOptions("UTC", summer).map((option) => option.value)).toEqual([
      "UTC",
      "Africa/Abidjan",
      "Europe/London",
    ]);
  });

  it("keeps a saved zone the browser does not know at the end", () => {
    vi.spyOn(Intl, "supportedValuesOf").mockReturnValue(["Europe/Moscow"]);

    expect(getTimezoneOptions("Mars/Olympus", winter)).toEqual([
      { value: "UTC", offset: "UTC+00:00" },
      { value: "Europe/Moscow", offset: "UTC+03:00" },
      { value: "Mars/Olympus", offset: null },
    ]);
  });

  it("falls back to UTC and the saved zone without Intl.supportedValuesOf", () => {
    vi.spyOn(Intl, "supportedValuesOf").mockImplementation(() => {
      throw new TypeError("not supported");
    });

    expect(getTimezoneOptions("Asia/Tokyo", winter).map((option) => option.value)).toEqual([
      "UTC",
      "Asia/Tokyo",
    ]);
  });
});

describe("formatTimezoneOffset", () => {
  const winter = new Date("2026-01-15T12:00:00Z");
  const summer = new Date("2026-07-15T12:00:00Z");

  it.each([
    ["UTC", winter, "UTC+00:00"],
    ["Europe/Moscow", winter, "UTC+03:00"],
    ["Asia/Kolkata", winter, "UTC+05:30"],
    ["America/New_York", winter, "UTC-05:00"],
    ["America/New_York", summer, "UTC-04:00"],
  ])("formats %s at %s as %s", (timezone, at, expected) => {
    expect(formatTimezoneOffset(timezone, at)).toBe(expected);
  });

  it("returns null for a zone the browser does not know", () => {
    expect(formatTimezoneOffset("Mars/Olympus", winter)).toBeNull();
  });
});
