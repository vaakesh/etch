import { createContext } from "react";
import { DEFAULT_THEME, type AppTheme, type ResolvedTheme } from "./theme";

export interface ThemeContextValue {
  theme: AppTheme;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: AppTheme) => void;
}

const defaultContextValue: ThemeContextValue = {
  theme: DEFAULT_THEME,
  resolvedTheme: "light",
  setTheme: () => undefined,
};

export const ThemeContext = createContext<ThemeContextValue>(defaultContextValue);
