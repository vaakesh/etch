import type { Locator } from "@playwright/test";

/** Activates a control the way the project's device does: tap on touch, click otherwise. */
export async function activate(control: Locator, hasTouch: boolean): Promise<void> {
  if (hasTouch) await control.tap();
  else await control.click();
}
