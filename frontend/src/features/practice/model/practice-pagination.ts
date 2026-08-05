import {
  DEFAULT_LOCALE,
  HIDDEN_CARD_COUNT_FORMS,
  localizeCount,
  type AppLocale,
} from "../../../i18n/localization";

const MAX_VISIBLE_PAGE_TOKENS = 7;
const INTERIOR_WINDOW_SIZE = MAX_VISIBLE_PAGE_TOKENS - 2;

interface PracticePaginationTokenBase {
  key: string;
  label: string;
  ariaLabel: string;
}

export interface PracticePaginationPageToken extends PracticePaginationTokenBase {
  type: "page";
  sequenceNumber: number;
  isCurrent: boolean;
}

export interface PracticePaginationEllipsisToken extends PracticePaginationTokenBase {
  type: "ellipsis";
  hiddenCount: number;
}

export type PracticePaginationToken = PracticePaginationPageToken | PracticePaginationEllipsisToken;

function createPageToken(
  sequenceNumber: number,
  index: number,
  currentSequenceNumber: number,
  locale: AppLocale,
): PracticePaginationPageToken {
  const isCurrent = sequenceNumber === currentSequenceNumber;
  const ariaLabel =
    locale === "en-US"
      ? isCurrent
        ? `Card ${sequenceNumber}, current`
        : `Go to card ${sequenceNumber}`
      : isCurrent
        ? `Карточка ${sequenceNumber}, текущая`
        : `Перейти к карточке ${sequenceNumber}`;

  return {
    type: "page",
    key: `page-${sequenceNumber}-${index}`,
    label: String(sequenceNumber),
    ariaLabel,
    sequenceNumber,
    isCurrent,
  };
}

function createEllipsisToken(
  position: "start" | "end",
  hiddenCount: number,
  locale: AppLocale,
): PracticePaginationEllipsisToken {
  return {
    type: "ellipsis",
    key: `ellipsis-${position}`,
    label: "…",
    ariaLabel: localizeCount(hiddenCount, HIDDEN_CARD_COUNT_FORMS, locale).text,
    hiddenCount,
  };
}

function getVisibleIndices(total: number, currentIndex: number): readonly number[] {
  if (total <= MAX_VISIBLE_PAGE_TOKENS) {
    return Array.from({ length: total }, (_, index) => index);
  }

  const centeredWindowStart = currentIndex - Math.floor(INTERIOR_WINDOW_SIZE / 2);
  const lastWindowStart = total - INTERIOR_WINDOW_SIZE - 1;
  const windowStart = Math.min(Math.max(centeredWindowStart, 1), lastWindowStart);
  const visibleIndices = [0];

  for (let index = windowStart; index < windowStart + INTERIOR_WINDOW_SIZE; index += 1) {
    visibleIndices.push(index);
  }

  visibleIndices.push(total - 1);
  return visibleIndices;
}

export function getPracticePaginationTokens(
  sequenceNumbers: readonly number[],
  currentSequenceNumber: number,
  locale: AppLocale = DEFAULT_LOCALE,
): readonly PracticePaginationToken[] {
  if (sequenceNumbers.length === 0) {
    return [];
  }

  const currentIndex = Math.max(sequenceNumbers.indexOf(currentSequenceNumber), 0);
  const visibleIndices = getVisibleIndices(sequenceNumbers.length, currentIndex);
  const tokens: PracticePaginationToken[] = [];
  let previousVisibleIndex: number | null = null;

  visibleIndices.forEach((visibleIndex) => {
    if (previousVisibleIndex !== null && visibleIndex - previousVisibleIndex > 1) {
      const hiddenCount = visibleIndex - previousVisibleIndex - 1;
      const position = previousVisibleIndex === 0 ? "start" : "end";
      tokens.push(createEllipsisToken(position, hiddenCount, locale));
    }

    tokens.push(
      createPageToken(sequenceNumbers[visibleIndex], visibleIndex, currentSequenceNumber, locale),
    );
    previousVisibleIndex = visibleIndex;
  });

  return tokens;
}
