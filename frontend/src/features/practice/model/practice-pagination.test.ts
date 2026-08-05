import { describe, expect, it } from "vitest";
import { getPracticePaginationTokens, type PracticePaginationToken } from "./practice-pagination";

function getPageNumbers(tokens: readonly PracticePaginationToken[]): readonly number[] {
  return tokens.flatMap((token) => (token.type === "page" ? [token.sequenceNumber] : []));
}

describe("getPracticePaginationTokens", () => {
  it("returns no tokens for an empty session", () => {
    expect(getPracticePaginationTokens([], 1)).toEqual([]);
  });

  it("shows every actual sequence number for a small sparse session", () => {
    expect(getPracticePaginationTokens([4, 9, 15], 9)).toEqual([
      {
        type: "page",
        key: "page-4-0",
        label: "4",
        ariaLabel: "Перейти к карточке 4",
        sequenceNumber: 4,
        isCurrent: false,
      },
      {
        type: "page",
        key: "page-9-1",
        label: "9",
        ariaLabel: "Карточка 9, текущая",
        sequenceNumber: 9,
        isCurrent: true,
      },
      {
        type: "page",
        key: "page-15-2",
        label: "15",
        ariaLabel: "Перейти к карточке 15",
        sequenceNumber: 15,
        isCurrent: false,
      },
    ]);
  });

  it("localizes page and ellipsis labels in English", () => {
    const tokens = getPracticePaginationTokens([1, 2, 3, 4, 5, 6, 7, 8, 9], 1, "en-US");

    expect(tokens[0]).toMatchObject({ ariaLabel: "Card 1, current" });
    expect(tokens[1]).toMatchObject({ ariaLabel: "Go to card 2" });
    expect(tokens).toContainEqual({
      type: "ellipsis",
      key: "ellipsis-end",
      label: "…",
      ariaLabel: "2 cards hidden",
      hiddenCount: 2,
    });
  });

  it("keeps seven numeric buttons at the beginning of a large session", () => {
    const sequenceNumbers = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    const tokens = getPracticePaginationTokens(sequenceNumbers, 10);

    expect(getPageNumbers(tokens)).toEqual([10, 20, 30, 40, 50, 60, 100]);
    expect(tokens).toContainEqual({
      type: "ellipsis",
      key: "ellipsis-end",
      label: "…",
      ariaLabel: "3 карточки пропущены",
      hiddenCount: 3,
    });
  });

  it("slides a five-card interior window around the current card", () => {
    const sequenceNumbers = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    const tokens = getPracticePaginationTokens(sequenceNumbers, 60);

    expect(getPageNumbers(tokens)).toEqual([10, 40, 50, 60, 70, 80, 100]);
    expect(tokens.filter((token) => token.type === "ellipsis")).toEqual([
      {
        type: "ellipsis",
        key: "ellipsis-start",
        label: "…",
        ariaLabel: "2 карточки пропущены",
        hiddenCount: 2,
      },
      {
        type: "ellipsis",
        key: "ellipsis-end",
        label: "…",
        ariaLabel: "1 карточка пропущена",
        hiddenCount: 1,
      },
    ]);
  });

  it("keeps seven numeric buttons at the end of a large session", () => {
    const sequenceNumbers = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    const tokens = getPracticePaginationTokens(sequenceNumbers, 100);

    expect(getPageNumbers(tokens)).toEqual([10, 50, 60, 70, 80, 90, 100]);
    expect(tokens.filter((token) => token.type === "ellipsis")).toHaveLength(1);
    expect(tokens).toContainEqual({
      type: "ellipsis",
      key: "ellipsis-start",
      label: "…",
      ariaLabel: "3 карточки пропущены",
      hiddenCount: 3,
    });
  });

  it("never invents a selectable sequence when the current value is absent", () => {
    const sequenceNumbers = [3, 8, 13, 21, 34, 55, 89, 144, 233];
    const tokens = getPracticePaginationTokens(sequenceNumbers, 999);
    const pageTokens = tokens.filter((token) => token.type === "page");

    expect(getPageNumbers(tokens)).toEqual([3, 8, 13, 21, 34, 55, 233]);
    expect(pageTokens.every((token) => !token.isCurrent)).toBe(true);
    expect(pageTokens.some((token) => token.sequenceNumber === 999)).toBe(false);
  });

  it("returns stable unique keys and never exceeds seven numeric tokens", () => {
    const sequenceNumbers = Array.from({ length: 100 }, (_, index) => (index + 1) * 3);
    const firstResult = getPracticePaginationTokens(sequenceNumbers, 153);
    const secondResult = getPracticePaginationTokens(sequenceNumbers, 153);
    const keys = firstResult.map((token) => token.key);

    expect(secondResult).toEqual(firstResult);
    expect(new Set(keys).size).toBe(keys.length);
    expect(getPageNumbers(firstResult)).toHaveLength(7);
    expect(getPageNumbers(firstResult).every((number) => sequenceNumbers.includes(number))).toBe(
      true,
    );
  });
});
