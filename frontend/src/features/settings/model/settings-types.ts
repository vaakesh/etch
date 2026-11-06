import type { AppLocale } from "../../../i18n";
import type { AppTheme } from "../../../theme";

export interface UserSettings {
  locale: AppLocale;
  showPreviewsForLong: boolean;
  theme: AppTheme;
  /** IANA-зона пользователя: от неё backend считает «сегодня» для повторений. */
  timezone: string;
}

export type UserSettingsUpdate = UserSettings;
