import { AUTH_ENDPOINTS, USER_ENDPOINTS, apiFetch } from "../../api";
import type { LoginCredentials, User } from "../model/auth-types";
import { parseCurrentUser } from "./auth-contract";

export async function loginRequest(
  credentials: LoginCredentials,
  signal?: AbortSignal,
): Promise<void> {
  await apiFetch<void, LoginCredentials>(AUTH_ENDPOINTS.login, {
    method: "POST",
    body: credentials,
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
