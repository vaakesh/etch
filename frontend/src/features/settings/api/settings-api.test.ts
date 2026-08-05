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

  it("updates both required settings through the backend contract", async () => {
    apiFetch.mockResolvedValue({ locale: "en-US", theme: "system" });

    await expect(updateUserSettingsRequest({ locale: "en-US", theme: "system" })).resolves.toEqual({
      locale: "en-US",
      theme: "system",
    });

    expect(apiFetch).toHaveBeenCalledWith("/users/me/settings", {
      method: "PATCH",
      body: { locale: "en-US", theme: "system" },
      signal: undefined,
    });
  });
});
