import { USER_ENDPOINTS, apiFetch } from "../../../api";
import { parseUserSettings } from "../model/settings-contract";
import type { UserSettings, UserSettingsUpdate } from "../model/settings-types";

export async function updateUserSettingsRequest(
  settings: UserSettingsUpdate,
  signal?: AbortSignal,
): Promise<UserSettings> {
  const response = await apiFetch<
    unknown,
    {
      locale: UserSettings["locale"];
      show_previews_for_long: boolean;
      theme: UserSettings["theme"];
    }
  >(USER_ENDPOINTS.settings, {
    method: "PATCH",
    body: {
      locale: settings.locale,
      show_previews_for_long: settings.showPreviewsForLong,
      theme: settings.theme,
    },
    signal,
  });

  return parseUserSettings(response);
}
