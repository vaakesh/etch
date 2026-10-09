import { expect } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";
import { captchaHeaders } from "./captcha";

export interface TestAccount {
  username: string;
  email: string;
  password: string;
}

const PASSWORD = "Integration-pass-1";
let sequence = 0;

/**
 * Credentials unique for this run, worker and call. The backend limits usernames to 18
 * characters of [A-Za-z0-9_-] and rejects special-use email domains such as .test.
 */
export function newAccountCredentials(workerIndex: number): TestAccount {
  sequence += 1;
  const username = `e2e_${Date.now().toString(36)}${workerIndex}${sequence}`.slice(0, 18);
  return { username, email: `${username}@example.com`, password: PASSWORD };
}

/** Precondition only: the account is created by the public registration endpoint. */
export async function registerAccount(api: APIRequestContext, account: TestAccount): Promise<void> {
  const response = await api.post("/api/users/create", {
    data: account,
    headers: await captchaHeaders(api),
  });
  expect(response.status(), `Register ${account.username}: ${await response.text()}`).toBe(201);
}

/**
 * Deletes an account through the public API with its own session. An account that was never
 * created (the scenario failed before registration) is skipped. Returns a problem description.
 */
export async function deleteAccount(
  api: APIRequestContext,
  account: TestAccount,
): Promise<string | null> {
  const login = await api.post("/api/auth/login", {
    data: { username: account.username, password: account.password },
    headers: await captchaHeaders(api),
  });
  if (login.status() === 404) return null;
  if (login.status() !== 204) {
    return `Cleanup login for ${account.username} answered ${login.status()}`;
  }
  const removal = await api.delete("/api/users/me");
  return removal.status() === 204
    ? null
    : `Cleanup DELETE /users/me for ${account.username} answered ${removal.status()}`;
}
