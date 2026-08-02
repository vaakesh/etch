import {
  DAY_COUNT_FORMS,
  DEFAULT_LOCALE,
  HOUR_SHORT_COUNT_FORMS,
  MINUTE_SHORT_COUNT_FORMS,
  SECOND_SHORT_COUNT_FORMS,
  formatNumber,
  localizeCount,
  type AppLocale,
} from "../../../i18n/localization";

const percentFormatters = new Map<AppLocale, Intl.NumberFormat>();
const weekdayFormatters = new Map<AppLocale, Intl.DateTimeFormat>();
const deckUpdatedAtFormatters = new Map<AppLocale, Intl.DateTimeFormat>();

function getPercentFormatter(locale: AppLocale): Intl.NumberFormat {
  const cachedFormatter = percentFormatters.get(locale);
  if (cachedFormatter !== undefined) {
    return cachedFormatter;
  }

  const formatter = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  percentFormatters.set(locale, formatter);
  return formatter;
}

function getWeekdayFormatter(locale: AppLocale): Intl.DateTimeFormat {
  const cachedFormatter = weekdayFormatters.get(locale);
  if (cachedFormatter !== undefined) {
    return cachedFormatter;
  }

  const formatter = new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" });
  weekdayFormatters.set(locale, formatter);
  return formatter;
}

function getDeckUpdatedAtFormatter(locale: AppLocale): Intl.DateTimeFormat {
  const cachedFormatter = deckUpdatedAtFormatters.get(locale);
  if (cachedFormatter !== undefined) {
    return cachedFormatter;
  }

  const formatter = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  deckUpdatedAtFormatters.set(locale, formatter);
  return formatter;
}

export function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, value));
}

export function formatCount(value: number, locale: AppLocale = DEFAULT_LOCALE): string {
  return formatNumber(Math.max(0, Math.trunc(value)), locale);
}

export function formatPercent(value: number, locale: AppLocale = DEFAULT_LOCALE): string {
  return `${getPercentFormatter(locale).format(clampPercent(value))}%`;
}

export function formatShortWeekday(date: string, locale: AppLocale = DEFAULT_LOCALE): string {
  const [year, month, day] = date.split("-").map(Number);
  const label = getWeekdayFormatter(locale).format(new Date(Date.UTC(year, month - 1, day)));

  return label.charAt(0).toLocaleUpperCase(locale) + label.slice(1);
}

export function formatDeckUpdatedAt(
  value: string | null,
  locale: AppLocale = DEFAULT_LOCALE,
): string | null {
  if (value === null) {
    return null;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return getDeckUpdatedAtFormatter(locale).format(date);
}

export function formatStudyTime(seconds: number, locale: AppLocale = DEFAULT_LOCALE): string {
  const safeSeconds = Math.max(0, Math.trunc(seconds));
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);

  if (hours > 0 && minutes > 0) {
    return `${localizeCount(hours, HOUR_SHORT_COUNT_FORMS, locale).text} ${
      localizeCount(minutes, MINUTE_SHORT_COUNT_FORMS, locale).text
    }`;
  }
  if (hours > 0) {
    return localizeCount(hours, HOUR_SHORT_COUNT_FORMS, locale).text;
  }
  if (minutes > 0) {
    return localizeCount(minutes, MINUTE_SHORT_COUNT_FORMS, locale).text;
  }

  return localizeCount(safeSeconds, SECOND_SHORT_COUNT_FORMS, locale).text;
}

export function formatStreak(days: number, locale: AppLocale = DEFAULT_LOCALE): string {
  return localizeCount(days, DAY_COUNT_FORMS, locale).text;
}
