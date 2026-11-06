import type { AppLocale } from "../../../i18n";

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

const relativeFormatters = new Map<AppLocale, Intl.RelativeTimeFormat>();
const dateTimeFormatters = new Map<AppLocale, Intl.DateTimeFormat>();

function getRelativeFormatter(locale: AppLocale): Intl.RelativeTimeFormat {
  let formatter = relativeFormatters.get(locale);
  if (formatter === undefined) {
    formatter = new Intl.RelativeTimeFormat(locale, { numeric: "always" });
    relativeFormatters.set(locale, formatter);
  }
  return formatter;
}

function getDateTimeFormatter(locale: AppLocale): Intl.DateTimeFormat {
  let formatter = dateTimeFormatters.get(locale);
  if (formatter === undefined) {
    formatter = new Intl.DateTimeFormat(locale, {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
    dateTimeFormatters.set(locale, formatter);
  }
  return formatter;
}

/**
 * Когда наступит следующий срок повторения: в пределах суток — относительно
 * текущего момента («через 3 часа»), дальше — датой и временем пользователя.
 */
export function formatNextReview(nextDueAt: string, now: Date, locale: AppLocale): string | null {
  const dueTime = Date.parse(nextDueAt);
  if (Number.isNaN(dueTime)) {
    return null;
  }

  const delta = dueTime - now.getTime();
  if (delta >= DAY_MS) {
    return getDateTimeFormatter(locale).format(dueTime);
  }
  if (delta >= HOUR_MS) {
    return getRelativeFormatter(locale).format(Math.round(delta / HOUR_MS), "hour");
  }

  // Срок мог уже наступить, пока страница была открыта: не показываем «… назад»
  return getRelativeFormatter(locale).format(Math.max(1, Math.ceil(delta / MINUTE_MS)), "minute");
}
