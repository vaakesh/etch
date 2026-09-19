import { describe, expect, it } from "vitest";
import type { CatalogPreviewCard } from "./catalog-types";
import {
  CATALOG_PREVIEW_CARD_PAGE_SIZE,
  getCatalogPreviewBatchOffset,
  getCatalogPreviewCardsForPage,
  getCatalogPreviewPageCount,
} from "./catalog-preview-pagination";

function createCards(count: number): readonly CatalogPreviewCard[] {
  return Array.from({ length: count }, (_, index) => ({
    uuid: `card-${index + 1}`,
    frontText: `Front ${index + 1}`,
    backText: `Back ${index + 1}`,
    frontLang: "en",
    backLang: "ru",
    updatedAt: "2026-07-17T10:30:00Z",
  }));
}

describe("catalog preview pagination", () => {
  it.each([
    [1, 0],
    [4, 0],
    [5, 100],
    [100, 2400],
  ])("maps page %s to batch offset %s", (page, expectedOffset) => {
    expect(getCatalogPreviewBatchOffset(page)).toBe(expectedOffset);
  });

  it("splits one loaded batch into four pages of 25 cards", () => {
    const cards = createCards(100);

    expect(getCatalogPreviewCardsForPage(cards, 0, 1)).toHaveLength(CATALOG_PREVIEW_CARD_PAGE_SIZE);
    expect(getCatalogPreviewCardsForPage(cards, 0, 4).map((card) => card.uuid)).toEqual([
      "card-76",
      "card-77",
      "card-78",
      "card-79",
      "card-80",
      "card-81",
      "card-82",
      "card-83",
      "card-84",
      "card-85",
      "card-86",
      "card-87",
      "card-88",
      "card-89",
      "card-90",
      "card-91",
      "card-92",
      "card-93",
      "card-94",
      "card-95",
      "card-96",
      "card-97",
      "card-98",
      "card-99",
      "card-100",
    ]);
  });

  it.each([
    [0, 0],
    [1, 1],
    [25, 1],
    [26, 2],
    [2500, 100],
  ])("maps %s cards to %s pages", (totalCardsCount, expectedPageCount) => {
    expect(getCatalogPreviewPageCount(totalCardsCount)).toBe(expectedPageCount);
  });
});
