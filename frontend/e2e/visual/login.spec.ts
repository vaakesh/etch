import { test, expect } from "../fixtures/visual-test";

test("[VIS-001] форма входа — светлая тема, русский язык", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "С возвращением", exact: true })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  await expect(page).toHaveScreenshot("login-light-ru.png");
});
