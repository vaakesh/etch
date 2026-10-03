import { describe, expect, it } from "vitest";
import {
  MAX_SESSION_SIZE,
  canPracticeEntireDeck,
  clampCustomSessionSize,
  getWordsPerSession,
  readCustomSessionSize,
} from "./practice-session-size";

describe("canPracticeEntireDeck", () => {
  it("allows the entire deck only up to the session limit", () => {
    expect(canPracticeEntireDeck(0)).toBe(true);
    expect(canPracticeEntireDeck(120)).toBe(true);
    expect(canPracticeEntireDeck(MAX_SESSION_SIZE)).toBe(true);
    expect(canPracticeEntireDeck(MAX_SESSION_SIZE + 1)).toBe(false);
    expect(canPracticeEntireDeck(5000)).toBe(false);
  });
});

describe("readCustomSessionSize", () => {
  it("treats an empty field as unusable but not invalid", () => {
    expect(readCustomSessionSize("")).toEqual({ value: null, isInvalid: false });
    expect(readCustomSessionSize("   ")).toEqual({ value: null, isInvalid: false });
  });

  it("accepts values inside the session limit", () => {
    expect(readCustomSessionSize("1")).toEqual({ value: 1, isInvalid: false });
    expect(readCustomSessionSize("250")).toEqual({ value: 250, isInvalid: false });
    expect(readCustomSessionSize(String(MAX_SESSION_SIZE))).toEqual({
      value: MAX_SESSION_SIZE,
      isInvalid: false,
    });
  });

  it("marks an over-limit value as invalid and lowers it to the limit", () => {
    expect(readCustomSessionSize("700")).toEqual({ value: MAX_SESSION_SIZE, isInvalid: true });
    expect(readCustomSessionSize("5000")).toEqual({ value: MAX_SESSION_SIZE, isInvalid: true });
  });

  it("marks values that are not positive integers as invalid and unusable", () => {
    expect(readCustomSessionSize("0")).toEqual({ value: null, isInvalid: true });
    expect(readCustomSessionSize("-5")).toEqual({ value: null, isInvalid: true });
    expect(readCustomSessionSize("1.5")).toEqual({ value: null, isInvalid: true });
    expect(readCustomSessionSize("abc")).toEqual({ value: null, isInvalid: true });
  });
});

describe("clampCustomSessionSize", () => {
  it("lowers an over-limit value to the session limit", () => {
    expect(clampCustomSessionSize("700")).toBe("500");
    expect(clampCustomSessionSize("5000")).toBe("500");
  });

  it("keeps every other input untouched", () => {
    expect(clampCustomSessionSize("")).toBe("");
    expect(clampCustomSessionSize("250")).toBe("250");
    expect(clampCustomSessionSize("500")).toBe("500");
    expect(clampCustomSessionSize("0")).toBe("0");
    expect(clampCustomSessionSize("abc")).toBe("abc");
  });
});

describe("getWordsPerSession", () => {
  it("caps the entire deck at the session limit", () => {
    expect(getWordsPerSession("all", 40, "")).toBe(40);
    expect(getWordsPerSession("all", MAX_SESSION_SIZE, "")).toBe(MAX_SESSION_SIZE);
    expect(getWordsPerSession("all", 4200, "")).toBe(MAX_SESSION_SIZE);
  });

  it("asks for a single card in an empty deck", () => {
    expect(getWordsPerSession("all", 0, "")).toBe(1);
  });

  it("returns the fixed presets", () => {
    expect(getWordsPerSession("50", 4200, "")).toBe(50);
    expect(getWordsPerSession("100", 4200, "")).toBe(100);
  });

  it("returns the custom value already capped at the session limit", () => {
    expect(getWordsPerSession("custom", 4200, "300")).toBe(300);
    expect(getWordsPerSession("custom", 4200, "700")).toBe(MAX_SESSION_SIZE);
    expect(getWordsPerSession("custom", 4200, "")).toBeNull();
    expect(getWordsPerSession("custom", 4200, "0")).toBeNull();
  });
});
