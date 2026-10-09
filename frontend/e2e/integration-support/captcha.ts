import { expect } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";
import { solveChallenge } from "altcha-lib";
import { deriveKey } from "altcha-lib/algorithms/pbkdf2";
import type { Challenge } from "altcha-lib/types";

/**
 * Headers for one captcha-protected API call (registration or login): a real challenge from the
 * stand, solved here. The backend accepts a solution once, so every call needs fresh headers.
 */
export async function captchaHeaders(api: APIRequestContext): Promise<Record<string, string>> {
  const response = await api.get("/api/auth/challenge");
  expect(response.status(), `Captcha challenge: ${await response.text()}`).toBe(200);
  const challenge = (await response.json()) as Challenge;
  const solution = await solveChallenge({ challenge, deriveKey });
  if (!solution) throw new Error("The stand captcha challenge was not solved");
  return { "X-Altcha": btoa(JSON.stringify({ challenge, solution })) };
}
