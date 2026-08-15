import type { AppLocale } from "../../../i18n";

const updatedAtFormatters = new Map<AppLocale, Intl.DateTimeFormat>();

function getUpdatedAtFormatter(locale: AppLocale): Intl.DateTimeFormat {
  const cachedFormatter = updatedAtFormatters.get(locale);
  if (cachedFormatter !== undefined) {
    return cachedFormatter;
  }

  const formatter = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  updatedAtFormatters.set(locale, formatter);
  return formatter;
}

export function formatCatalogUpdatedAt(value: string | null, locale: AppLocale): string | null {
  if (value === null) {
    return null;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : getUpdatedAtFormatter(locale).format(date);
}
