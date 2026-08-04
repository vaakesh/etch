import { useEffect, useMemo, useState, type ReactNode } from "react";
import { LocaleContext, type LocaleContextValue } from "./locale-context";
import { DEFAULT_LOCALE, isSupportedLocale, type AppLocale } from "./localization";

const LOCALE_STORAGE_KEY = "etch.locale";

interface LocaleProviderProps {
  children: ReactNode;
  initialLocale?: AppLocale;
}

function readStoredLocale(): AppLocale {
  if (typeof window === "undefined") {
    return DEFAULT_LOCALE;
  }

  try {
    const storedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    return isSupportedLocale(storedLocale) ? storedLocale : DEFAULT_LOCALE;
  } catch {
    return DEFAULT_LOCALE;
  }
}

export function LocaleProvider({ children, initialLocale }: LocaleProviderProps) {
  const [locale, setLocale] = useState<AppLocale>(() => initialLocale ?? readStoredLocale());

  useEffect(() => {
    document.documentElement.lang = locale;

    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    } catch {
      // The locale still works for the current session when storage is unavailable.
    }
  }, [locale]);

  const contextValue = useMemo<LocaleContextValue>(() => ({ locale, setLocale }), [locale]);

  return <LocaleContext.Provider value={contextValue}>{children}</LocaleContext.Provider>;
}
