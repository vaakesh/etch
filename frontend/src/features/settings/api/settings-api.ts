import { USER_ENDPOINTS, apiFetch } from "../../../api";
import { parseUserSettings } from "../model/settings-contract";
import type { UserSettings, UserSettingsUpdate } from "../model/settings-types";

export async function updateUserSettingsRequest(
  settings: UserSettingsUpdate,
  signal?: AbortSignal,
): Promise<UserSettings> {
  const response = await apiFetch<unknown, UserSettingsUpdate>(USER_ENDPOINTS.settings, {
    method: "PATCH",
    body: settings,
    signal,
  });

  return parseUserSettings(response);
}
