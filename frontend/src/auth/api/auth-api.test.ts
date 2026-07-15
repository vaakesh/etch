import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }));

vi.mock("../../api", () => ({
  AUTH_ENDPOINTS: {
    login: "/auth/login",
    logout: "/auth/logout",
    refresh: "/auth/refresh",
  },
  USER_ENDPOINTS: { me: "/users/me" },
  apiFetch,
}));

import { getCurrentUser, loginRequest, refreshSessionRequest } from "./auth-api";

describe("auth API", () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });

  it("loads the authenticated user from /users/me", async () => {
    apiFetch.mockResolvedValue({
      uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
      username: "alice",
      email: "alice@example.com",
    });

    await expect(getCurrentUser()).resolves.toEqual({
      uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
      username: "alice",
      email: "alice@example.com",
    });
    expect(apiFetch).toHaveBeenCalledWith("/users/me", {
      signal: undefined,
      retryOnUnauthorized: true,
    });
  });

  it("sends login credentials as an OAuth2 form for the cookie session", async () => {
    apiFetch.mockResolvedValue(undefined);

    await loginRequest({ username: "alice", password: "password" });

    const [path, options] = apiFetch.mock.calls[0] ?? [];
    expect(path).toBe("/auth/login");
    expect(options).toMatchObject({
      method: "POST",
      auth: false,
      retryOnUnauthorized: false,
    });
    expect(options.body).toBeInstanceOf(URLSearchParams);
    expect(options.body.toString()).toBe("username=alice&password=password");
  });

  it("refreshes the cookie session without exposing response tokens", async () => {
    apiFetch.mockResolvedValue(undefined);

    await expect(refreshSessionRequest(new AbortController().signal)).resolves.toBeUndefined();
    expect(apiFetch).toHaveBeenCalledWith(
      "/auth/refresh",
      expect.objectContaining({
        method: "POST",
        auth: false,
        retryOnUnauthorized: false,
      }),
    );
  });
});
