import { test, expect } from "../fixtures/mocked-test";
import { buildCurrentUser, buildEmptyHome } from "../data/builders";
import { expectNoHorizontalOverflow } from "../helpers/layout";
import { mockEmptyReviewSummary } from "../mocks/home";

test.use({ currentUser: buildCurrentUser() });

test(
  "[HOME-001] авторизованный пользователь видит пустую главную после reload",
  { tag: ["@smoke", "@responsive"] },
  async ({ page, api }) => {
    api.on("GET", "/bff/home", async ({ route, url }) => {
      expect(url.search).toBe("");
      await route.fulfill({ json: buildEmptyHome() });
    });
    mockEmptyReviewSummary(api);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
    await expect(page.getByText("Здесь появятся ваши колоды", { exact: true })).toBeVisible();
    await expect(page.getByText("Пока нечего повторять", { exact: true })).toBeVisible();
    await expectNoHorizontalOverflow(page);
    await page.reload();
    await expect(page).toHaveURL("/");
    await expect(page.getByText("Здесь появятся ваши колоды", { exact: true })).toBeVisible();
  },
);
