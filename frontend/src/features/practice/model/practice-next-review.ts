import type { AppLocale } from "../../../i18n";

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;
const MONTH_MS = 30 * DAY_MS;
const YEAR_MS = 365 * DAY_MS;

const formatters = new Map<AppLocale, Intl.RelativeTimeFormat>();

function getFormatter(locale: AppLocale): Intl.RelativeTimeFormat {
  let formatter = formatters.get(locale);
  if (formatter === undefined) {
    // auto: «завтра» вместо «через 1 день»
    formatter = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
    formatters.set(locale, formatter);
  }
  return formatter;
}

/**
 * Через сколько слово вернётся на повторение после оценки: «через 10 минут», «завтра»,
 * «через 4 дня». Срок FSRS всегда в будущем, но часы клиента могут отставать от сервера,
 * поэтому меньше минуты не показывается.
 */
export function formatNextReviewIn(
  nextReviewAt: string,
  now: Date,
  locale: AppLocale,
): string | null {
  const dueTime = Date.parse(nextReviewAt);
  if (Number.isNaN(dueTime)) {
    return null;
  }

  const delta = dueTime - now.getTime();
  const formatter = getFormatter(locale);
  if (delta < HOUR_MS) {
    return formatter.format(Math.max(1, Math.round(delta / MINUTE_MS)), "minute");
  }
  if (delta < DAY_MS) {
    return formatter.format(Math.round(delta / HOUR_MS), "hour");
  }
  if (delta < MONTH_MS) {
    return formatter.format(Math.round(delta / DAY_MS), "day");
  }
  if (delta < YEAR_MS) {
    return formatter.format(Math.round(delta / MONTH_MS), "month");
  }
  return formatter.format(Math.round(delta / YEAR_MS), "year");
}
