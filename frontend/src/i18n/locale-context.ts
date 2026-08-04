import { createContext } from "react";
import { DEFAULT_LOCALE, type AppLocale } from "./localization";

export interface LocaleContextValue {
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
}

const defaultContextValue: LocaleContextValue = {
  locale: DEFAULT_LOCALE,
  setLocale: () => undefined,
};

export const LocaleContext = createContext<LocaleContextValue>(defaultContextValue);
