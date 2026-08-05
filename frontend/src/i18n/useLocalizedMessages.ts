import type { AppLocale } from "./localization";
import { useLocale } from "./useLocale";

export function useLocalizedMessages<T>(messages: Readonly<Record<AppLocale, T>>): T {
  const { locale } = useLocale();
  return messages[locale];
}
