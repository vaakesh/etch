import { test as base, expect } from "./mocked-test";

export const test = base.extend<{ visualClock: void }>({
  visualClock: [
    async ({ page }, runFixture) => {
      // Keep timers running; fix Date only, so startup animations and async UI can finish.
      await page.clock.setFixedTime(new Date("2026-01-15T09:00:00Z"));
      await runFixture();
    },
    { auto: true },
  ],
});
export { expect };
