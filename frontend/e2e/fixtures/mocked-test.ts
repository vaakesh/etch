import { test as base, expect } from "./base-test";
import type { CurrentUserResponse } from "../data/builders";
import { ApiMockRouter } from "../mocks/api-router";
import { AuthMock } from "../mocks/auth";

export const test = base.extend<{
  currentUser: CurrentUserResponse | null;
  api: ApiMockRouter;
  auth: AuthMock;
}>({
  currentUser: [null, { option: true }],
  api: [
    async ({ context, baseURL }, runFixture, testInfo) => {
      if (!baseURL) throw new Error("Mocked tests require baseURL");
      const origin = new URL(baseURL).origin;
      const api = new ApiMockRouter(baseURL);
      // Registered first: specific API routes take precedence over this boundary.
      await context.route("**/*", async (route) => {
        const url = new URL(route.request().url());
        if (url.origin === origin) {
          await route.continue();
        } else {
          api.unexpected.push(`External request: ${url.origin}${url.pathname}`);
          await route.abort("blockedbyclient");
        }
      });
      await api.install(context);
      try {
        await runFixture(api);
      } finally {
        api.openAllGates();
        await context.unrouteAll({ behavior: "wait" });
        if (api.unexpected.length) {
          await testInfo.attach("unexpected-requests", {
            body: api.unexpected.join("\n"),
            contentType: "text/plain",
          });
        }
        expect(api.unexpected, "Every API/external request must be explicitly handled").toEqual([]);
      }
    },
    { auto: true },
  ],
  // Auto: every mocked test needs the bootstrap session answers before the first navigation.
  auth: [
    async ({ api, diagnostics, currentUser }, runFixture) => {
      await runFixture(new AuthMock(api, diagnostics, structuredClone(currentUser)));
    },
    { auto: true },
  ],
});
export { expect };
