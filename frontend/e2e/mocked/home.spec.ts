import { test, expect } from "../fixtures/mocked-test";
import { buildCurrentUser, buildEmptyHome } from "../data/builders";
import { expectNoHorizontalOverflow } from "../helpers/layout";

test.use({ currentUser: buildCurrentUser() });

test(
  "[HOME-001] авторизованный пользователь видит пустую главную после reload",
  { tag: ["@smoke", "@responsive"] },
  async ({ page, api }) => {
    api.on("GET", "/bff/home", async ({ route, url }) => {
      expect(url.search).toBe("");
      await route.fulfill({ json: buildEmptyHome() });
    });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
    await expect(page.getByText("Здесь появятся ваши колоды", { exact: true })).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await page.reload();
    await expect(page).toHaveURL("/");
    await expect(page.getByText("Здесь появятся ваши колоды", { exact: true })).toBeVisible();
  },
);
