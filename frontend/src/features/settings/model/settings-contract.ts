import { ApiError } from "../../../api/api-error";
import { isSupportedLocale } from "../../../i18n";
import { isAppTheme } from "../../../theme";
import type { UserSettings } from "./settings-types";

export class SettingsContractError extends ApiError {
  constructor(message: string) {
    super({ status: 0, code: "INVALID_SETTINGS_RESPONSE", message });
    this.name = "SettingsContractError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function parseUserSettings(payload: unknown): UserSettings {
  if (
    !isRecord(payload) ||
    !isSupportedLocale(payload.locale) ||
    !isAppTheme(payload.theme) ||
    typeof payload.show_previews_for_long !== "boolean"
  ) {
    throw new SettingsContractError("The backend returned an unexpected settings shape.");
  }

  return {
    locale: payload.locale,
    showPreviewsForLong: payload.show_previews_for_long,
    theme: payload.theme,
  };
}
