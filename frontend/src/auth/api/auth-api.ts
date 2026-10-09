import { AUTH_ENDPOINTS, USER_ENDPOINTS, apiFetch } from "../../api";
import type { LoginCredentials, RegistrationCredentials, User } from "../model/auth-types";
import { parseCurrentUser } from "./auth-contract";
import { CAPTCHA_HEADER, solveCaptcha } from "./captcha-api";

export async function registerRequest(
  credentials: RegistrationCredentials,
  signal?: AbortSignal,
): Promise<User> {
  const captcha = await solveCaptcha(signal);
  const response = await apiFetch<unknown, RegistrationCredentials>(USER_ENDPOINTS.create, {
    method: "POST",
    body: credentials,
    headers: { [CAPTCHA_HEADER]: captcha },
    auth: false,
    retryOnUnauthorized: false,
    signal,
  });
  return parseCurrentUser(response);
}

export async function loginRequest(
  credentials: LoginCredentials,
  signal?: AbortSignal,
): Promise<void> {
  const captcha = await solveCaptcha(signal);
  await apiFetch<void, LoginCredentials>(AUTH_ENDPOINTS.login, {
    method: "POST",
    body: credentials,
    headers: { [CAPTCHA_HEADER]: captcha },
    auth: false,
    retryOnUnauthorized: false,
    signal,
  });
}

export async function refreshSessionRequest(signal: AbortSignal): Promise<void> {
  await apiFetch<void>(AUTH_ENDPOINTS.refresh, {
    method: "POST",
    auth: false,
    retryOnUnauthorized: false,
    signal,
  });
}

export async function logoutRequest(signal?: AbortSignal): Promise<void> {
  await apiFetch<void>(AUTH_ENDPOINTS.logout, {
    method: "POST",
    auth: false,
    retryOnUnauthorized: false,
    signal,
  });
}

export async function getCurrentUser(
  signal?: AbortSignal,
  retryOnUnauthorized = true,
): Promise<User> {
  const response = await apiFetch<unknown>(USER_ENDPOINTS.me, {
    signal,
    retryOnUnauthorized,
  });
  return parseCurrentUser(response);
}
