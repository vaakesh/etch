import { test as base, expect } from "./base-test";
import {
  deleteAccount,
  newAccountCredentials,
  registerAccount,
} from "../integration-support/accounts";
import type { TestAccount } from "../integration-support/accounts";
import { flushTestRedis } from "../integration-support/redis";
import { installLocalFonts } from "./local-fonts";

export interface Accounts {
  /** Credentials for an account the scenario registers itself through the UI. */
  reserve(): TestAccount;
  /** An account that already exists on the stand, registered through the API as a precondition. */
  create(): Promise<TestAccount>;
}

export const test = base.extend<{ cleanRedis: void; standReady: void; accounts: Accounts }>({
  // Every test starts and ends with an empty test Redis, so the per-IP rate limits of
  // registration and login never carry over between tests or runs.
  cleanRedis: [
    async ({ baseURL }, runFixture) => {
      if (!baseURL) throw new Error("Integration requires a dedicated test frontend URL");
      await flushTestRedis();
      try {
        await runFixture();
      } finally {
        await flushTestRedis();
      }
    },
    { auto: true },
  ],

  // Every account of the test is deleted afterwards through its own separate API session, so
  // cleanup works after logout and does not touch the cookies of the browser context. Depends on
  // cleanRedis: the final flush runs after the cleanup logins.
  accounts: async ({ playwright, baseURL, cleanRedis }, runFixture, testInfo) => {
    void cleanRedis;
    const api = await playwright.request.newContext({ baseURL });
    const owned: TestAccount[] = [];
    const reserve = (): TestAccount => {
      const account = newAccountCredentials(testInfo.parallelIndex);
      owned.push(account);
      return account;
    };
    try {
      await runFixture({
        reserve,
        create: async () => {
          const account = reserve();
          await registerAccount(api, account);
          return account;
        },
      });
    } finally {
      const problems: string[] = [];
      for (const account of owned) {
        const problem = await deleteAccount(api, account);
        if (problem) problems.push(problem);
      }
      await api.dispose();
      if (problems.length) {
        await testInfo.attach("cleanup-problems", {
          body: problems.join("\n"),
          contentType: "text/plain",
        });
      }
      // Soft: a cleanup problem is reported without hiding the original failure.
      expect.soft(problems, "Accounts created by the test must be deleted").toEqual([]);
    }
  },

  standReady: [
    async ({ context, baseURL, diagnostics }, runFixture) => {
      if (!baseURL) throw new Error("Integration requires a dedicated test frontend URL");
      // The browser and setup use the same frontend origin and real /api proxy.
      const response = await context.request.get("/api/ready", { timeout: 10_000 });
      expect(response.status(), "Test API readiness through frontend proxy").toBe(200);
      expect(await response.json()).toEqual({ status: "ready" });
      diagnostics.expectHttpError({
        method: "GET",
        pathname: "/api/users/me",
        status: 401,
        reason: "Fresh guest context has no access cookie",
      });
      diagnostics.expectHttpError({
        method: "POST",
        pathname: "/api/auth/refresh",
        status: 401,
        reason: "Fresh guest context has no refresh cookie",
      });
      await installLocalFonts(context, baseURL);
      await runFixture();
    },
    { auto: true },
  ],
});
export { expect };
