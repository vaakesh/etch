import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ThemeContext, type ThemeContextValue } from "./theme-context";
import {
  DEFAULT_THEME,
  isAppTheme,
  resolveTheme,
  type AppTheme,
  type ResolvedTheme,
} from "./theme";

const THEME_STORAGE_KEY = "etch.theme";
const DARK_THEME_MEDIA_QUERY = "(prefers-color-scheme: dark)";

interface ThemeProviderProps {
  children: ReactNode;
  initialTheme?: AppTheme;
}

function readStoredTheme(): AppTheme {
  if (typeof window === "undefined") {
    return DEFAULT_THEME;
  }

  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isAppTheme(storedTheme) ? storedTheme : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

function readPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia(DARK_THEME_MEDIA_QUERY).matches;
}

function getThemeColor(theme: ResolvedTheme): string {
  return theme === "dark" ? "#171426" : "#c3b8f5";
}

export function ThemeProvider({ children, initialTheme }: ThemeProviderProps) {
  const [theme, setTheme] = useState<AppTheme>(() => initialTheme ?? readStoredTheme());
  const [prefersDark, setPrefersDark] = useState(readPrefersDark);
  const resolvedTheme = resolveTheme(theme, prefersDark);

  useEffect(() => {
    const mediaQuery = window.matchMedia(DARK_THEME_MEDIA_QUERY);
    const handleChange = (event: MediaQueryListEvent): void => {
      setPrefersDark(event.matches);
    };

    mediaQuery.addEventListener("change", handleChange);

    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.style.colorScheme = resolvedTheme;
    document
      .querySelector<HTMLMetaElement>('meta[name="theme-color"]')
      ?.setAttribute("content", getThemeColor(resolvedTheme));

    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // The selected theme still works for the current session when storage is unavailable.
    }
  }, [resolvedTheme, theme]);

  const contextValue = useMemo<ThemeContextValue>(
    () => ({ theme, resolvedTheme, setTheme }),
    [resolvedTheme, theme],
  );

  return <ThemeContext.Provider value={contextValue}>{children}</ThemeContext.Provider>;
}
