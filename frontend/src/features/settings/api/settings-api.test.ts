import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }));

vi.mock("../../../api", () => ({
  USER_ENDPOINTS: {
    me: "/users/me",
    settings: "/users/me/settings",
  },
  apiFetch,
}));

import { updateUserSettingsRequest } from "./settings-api";

describe("settings API", () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });

  it("updates all user settings through the backend contract", async () => {
    apiFetch.mockResolvedValue({
      locale: "en-US",
      theme: "system",
      show_previews_for_long: false,
    });

    await expect(
      updateUserSettingsRequest({
        locale: "en-US",
        showPreviewsForLong: false,
        theme: "system",
      }),
    ).resolves.toEqual({
      locale: "en-US",
      showPreviewsForLong: false,
      theme: "system",
    });

    expect(apiFetch).toHaveBeenCalledWith("/users/me/settings", {
      method: "PATCH",
      body: { locale: "en-US", show_previews_for_long: false, theme: "system" },
      signal: undefined,
    });
  });
});
