import type { CatalogPreviewCard } from "./catalog-types";

export const CATALOG_PREVIEW_CARD_BATCH_SIZE = 100;
export const CATALOG_PREVIEW_CARD_PAGE_SIZE = 25;

const PAGES_PER_BATCH = CATALOG_PREVIEW_CARD_BATCH_SIZE / CATALOG_PREVIEW_CARD_PAGE_SIZE;

export function getCatalogPreviewPageCount(totalCardsCount: number): number {
  return Math.ceil(Math.max(0, totalCardsCount) / CATALOG_PREVIEW_CARD_PAGE_SIZE);
}

export function getCatalogPreviewBatchOffset(page: number): number {
  const safePage = Math.max(1, Math.floor(page));
  return Math.floor((safePage - 1) / PAGES_PER_BATCH) * CATALOG_PREVIEW_CARD_BATCH_SIZE;
}

export function getCatalogPreviewCardsForPage(
  cards: readonly CatalogPreviewCard[],
  batchOffset: number,
  page: number,
): readonly CatalogPreviewCard[] {
  const pageOffset = (Math.max(1, Math.floor(page)) - 1) * CATALOG_PREVIEW_CARD_PAGE_SIZE;
  const startIndex = pageOffset - batchOffset;

  if (startIndex < 0 || startIndex >= cards.length) {
    return [];
  }

  return cards.slice(startIndex, startIndex + CATALOG_PREVIEW_CARD_PAGE_SIZE);
}
