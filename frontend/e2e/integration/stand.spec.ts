import { test, expect } from "../fixtures/integration-test";

test(
  "[ENV-001] настоящий API через proxy и гостевая страница доступны",
  { tag: "@smoke" },
  async ({ page }) => {
    const currentUser = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/api/users/me" &&
        response.request().method() === "GET",
    );
    await page.goto("/login");
    expect((await currentUser).status()).toBe(401);
    await expect(page.getByRole("heading", { name: "С возвращением", exact: true })).toBeVisible();
    await expect(
      page.getByRole("textbox", { name: "Имя пользователя", exact: true }),
    ).toBeVisible();
  },
);
