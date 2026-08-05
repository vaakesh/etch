import { useEffect } from "react";
import { useAuth } from "../auth/hooks/useAuth";
import { useLocale } from "../i18n";
import { useTheme } from "../theme";

export function UserPreferencesSync() {
  const { status, user } = useAuth();
  const { setLocale } = useLocale();
  const { setTheme } = useTheme();
  const locale = user?.settings.locale;
  const theme = user?.settings.theme;

  useEffect(() => {
    if (status !== "authorized" || locale === undefined || theme === undefined) {
      return;
    }

    setLocale(locale);
    setTheme(theme);
  }, [locale, setLocale, setTheme, status, theme]);

  return null;
}
