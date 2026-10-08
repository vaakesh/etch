import { expect } from "@playwright/test";
import type { Page } from "@playwright/test";

export async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  await expect
    .poll(
      () =>
        page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        ),
      { message: "Page must fit the viewport horizontally" },
    )
    .toBeLessThanOrEqual(1);
}
