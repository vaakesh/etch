import { describe, expect, it } from "vitest";
import {
  getCatalogPaginationTokens,
  parseCatalogPage,
  type CatalogPaginationToken,
} from "./catalog-pagination";

function getPageNumbers(tokens: readonly CatalogPaginationToken[]): readonly number[] {
  return tokens.flatMap((token) => (token.type === "page" ? [token.pageNumber] : []));
}

describe("parseCatalogPage", () => {
  it.each([
    [null, 1],
    ["", 1],
    ["0", 1],
    ["-2", 1],
    ["2.5", 1],
    ["three", 1],
    ["3", 3],
  ])("maps %s to page %s", (value, expectedPage) => {
    expect(parseCatalogPage(value)).toBe(expectedPage);
  });
});

describe("getCatalogPaginationTokens", () => {
  it("shows every page when the catalog has a short page range", () => {
    expect(getPageNumbers(getCatalogPaginationTokens(4, 2))).toEqual([1, 2, 3, 4]);
  });

  it("keeps the first, nearby, and last pages around the current page", () => {
    expect(getCatalogPaginationTokens(10, 5)).toEqual([
      { type: "page", key: "page-1", pageNumber: 1 },
      { type: "ellipsis", key: "ellipsis-0-3" },
      { type: "page", key: "page-4", pageNumber: 4 },
      { type: "page", key: "page-5", pageNumber: 5 },
      { type: "page", key: "page-6", pageNumber: 6 },
      { type: "ellipsis", key: "ellipsis-5-9" },
      { type: "page", key: "page-10", pageNumber: 10 },
    ]);
  });

  it("never renders more than five numbered buttons", () => {
    const tokens = getCatalogPaginationTokens(100, 84);

    expect(getPageNumbers(tokens)).toHaveLength(5);
    expect(getPageNumbers(tokens)).toEqual([1, 83, 84, 85, 100]);
  });
});
