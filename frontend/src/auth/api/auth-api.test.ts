import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }));

const { solveCaptcha } = vi.hoisted(() => ({ solveCaptcha: vi.fn() }));

vi.mock("../../api", () => ({
  AUTH_ENDPOINTS: {
    login: "/auth/login",
    logout: "/auth/logout",
    refresh: "/auth/refresh",
  },
  USER_ENDPOINTS: { create: "/users/create", me: "/users/me" },
  apiFetch,
}));

vi.mock("./captcha-api", () => ({ CAPTCHA_HEADER: "X-Altcha", solveCaptcha }));

import { getCurrentUser, loginRequest, refreshSessionRequest, registerRequest } from "./auth-api";

describe("auth API", () => {
  beforeEach(() => {
    apiFetch.mockReset();
    solveCaptcha.mockReset();
    solveCaptcha.mockResolvedValue("solved-captcha");
  });

  it("loads the authenticated user from /users/me", async () => {
    apiFetch.mockResolvedValue({
      uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
      username: "alice",
      email: "alice@example.com",
      settings: { locale: "ru-RU", theme: "light", show_previews_for_long: true },
    });

    await expect(getCurrentUser()).resolves.toEqual({
      uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
      username: "alice",
      email: "alice@example.com",
      settings: { locale: "ru-RU", showPreviewsForLong: true, theme: "light" },
    });
    expect(apiFetch).toHaveBeenCalledWith("/users/me", {
      signal: undefined,
      retryOnUnauthorized: true,
    });
  });

  it("sends login credentials as the JSON request expected by LoginRequest", async () => {
    apiFetch.mockResolvedValue(undefined);

    await loginRequest({ username: "alice", password: "password" });

    const [path, options] = apiFetch.mock.calls[0] ?? [];
    expect(path).toBe("/auth/login");
    expect(options).toMatchObject({
      method: "POST",
      auth: false,
      retryOnUnauthorized: false,
    });
    expect(options.body).toEqual({ username: "alice", password: "password" });
    expect(options.headers).toEqual({ "X-Altcha": "solved-captcha" });
  });

  it("solves a separate captcha for login and for registration", async () => {
    const signal = new AbortController().signal;
    apiFetch.mockResolvedValue({
      uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
      username: "alice",
      email: "alice@example.com",
      settings: { locale: "ru-RU", theme: "light", show_previews_for_long: true },
    });

    await registerRequest(
      { username: "alice", email: "alice@example.com", password: "password" },
      signal,
    );
    await loginRequest({ username: "alice", password: "password" }, signal);

    expect(solveCaptcha).toHaveBeenCalledTimes(2);
    expect(solveCaptcha).toHaveBeenCalledWith(signal);
  });

  it("does not send credentials when the captcha cannot be solved", async () => {
    solveCaptcha.mockRejectedValue(new Error("captcha failed"));

    await expect(loginRequest({ username: "alice", password: "password" })).rejects.toThrow(
      "captcha failed",
    );
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("creates a user through the public registration endpoint", async () => {
    apiFetch.mockResolvedValue({
      uuid: "3bc4b650-292f-480f-b1bb-3f5414269714",
      username: "alice",
      email: "alice@example.com",
      created_at: "2026-08-14T12:00:00Z",
      updated_at: "2026-08-14T12:00:00Z",
      settings: { locale: "ru-RU", theme: "light", show_previews_for_long: true },
    });

    await expect(
      registerRequest({
        username: "alice",
        email: "alice@example.com",
        password: "password",
      }),
    ).resolves.toMatchObject({
      username: "alice",
      email: "alice@example.com",
    });
    expect(apiFetch).toHaveBeenCalledWith("/users/create", {
      method: "POST",
      body: {
        username: "alice",
        email: "alice@example.com",
        password: "password",
      },
      headers: { "X-Altcha": "solved-captcha" },
      auth: false,
      retryOnUnauthorized: false,
      signal: undefined,
    });
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
