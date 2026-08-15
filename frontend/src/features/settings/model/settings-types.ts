import type { AppLocale } from "../../../i18n";
import type { AppTheme } from "../../../theme";

export interface UserSettings {
  locale: AppLocale;
  showPreviewsForLong: boolean;
  theme: AppTheme;
}

export type UserSettingsUpdate = UserSettings;
