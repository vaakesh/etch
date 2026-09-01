const MAX_VISIBLE_PAGE_BUTTONS = 5;
const INTERIOR_WINDOW_SIZE = MAX_VISIBLE_PAGE_BUTTONS - 2;

export interface CatalogPaginationPageToken {
  type: "page";
  key: string;
  pageNumber: number;
}

export interface CatalogPaginationEllipsisToken {
  type: "ellipsis";
  key: string;
}

export type CatalogPaginationToken = CatalogPaginationPageToken | CatalogPaginationEllipsisToken;

function getVisiblePageIndices(pageCount: number, currentPage: number): readonly number[] {
  if (pageCount <= MAX_VISIBLE_PAGE_BUTTONS) {
    return Array.from({ length: pageCount }, (_, index) => index);
  }

  const currentIndex = Math.min(Math.max(currentPage - 1, 0), pageCount - 1);
  const centeredWindowStart = currentIndex - Math.floor(INTERIOR_WINDOW_SIZE / 2);
  const lastWindowStart = pageCount - INTERIOR_WINDOW_SIZE - 1;
  const windowStart = Math.min(Math.max(centeredWindowStart, 1), lastWindowStart);
  const visibleIndices = [0];

  for (let index = windowStart; index < windowStart + INTERIOR_WINDOW_SIZE; index += 1) {
    visibleIndices.push(index);
  }

  visibleIndices.push(pageCount - 1);
  return visibleIndices;
}

export function parseCatalogPage(value: string | null): number {
  if (value === null || !/^[1-9]\d*$/.test(value)) {
    return 1;
  }

  const page = Number(value);
  return Number.isSafeInteger(page) ? page : 1;
}

export function getCatalogPaginationTokens(
  pageCount: number,
  currentPage: number,
): readonly CatalogPaginationToken[] {
  const safePageCount = Math.max(1, Math.floor(pageCount));
  const visibleIndices = getVisiblePageIndices(safePageCount, currentPage);
  const tokens: CatalogPaginationToken[] = [];
  let previousVisibleIndex: number | null = null;

  visibleIndices.forEach((visibleIndex) => {
    if (previousVisibleIndex !== null && visibleIndex - previousVisibleIndex > 1) {
      tokens.push({
        type: "ellipsis",
        key: `ellipsis-${previousVisibleIndex}-${visibleIndex}`,
      });
    }

    const pageNumber = visibleIndex + 1;
    tokens.push({ type: "page", key: `page-${pageNumber}`, pageNumber });
    previousVisibleIndex = visibleIndex;
  });

  return tokens;
}
