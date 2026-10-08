import { test, expect } from "../fixtures/mocked-test";
import { expectNoHorizontalOverflow } from "../helpers/layout";

test(
  "[AUTH-001] гость переключается с входа на регистрацию",
  { tag: ["@smoke", "@responsive"] },
  async ({ page, isMobile }) => {
    await test.step("Открыть вход без сессии", async () => {
      await page.goto("/login");
      await expect(
        page.getByRole("heading", { name: "С возвращением", exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("textbox", { name: "Имя пользователя", exact: true }),
      ).toBeVisible();
    });
    await test.step("Переключить режим обычным действием пользователя", async () => {
      const register = page.getByRole("button", { name: "Регистрация", exact: true });
      if (isMobile) await register.tap();
      else await register.click();
      await expect(
        page.getByRole("heading", { name: "Начните с Etch", exact: true }),
      ).toBeVisible();
      await expect(page.getByRole("textbox", { name: "Email", exact: true })).toBeVisible();
      await expectNoHorizontalOverflow(page);
    });
  },
);

test(
  "[AUTH-002] protected deep link без сессии открывает вход",
  { tag: "@smoke" },
  async ({ page }) => {
    await page.goto("/settings");
    await expect(page).toHaveURL(/\/login(?:\?|$)/);
    await expect(page.getByRole("heading", { name: "С возвращением", exact: true })).toBeVisible();
  },
);
