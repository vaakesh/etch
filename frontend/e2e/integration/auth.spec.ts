import { test, expect } from "../fixtures/integration-test";
import type { Page } from "@playwright/test";
import { authForm, enterField, fillLoginForm } from "../helpers/auth-form";

async function expectHome(page: Page): Promise<void> {
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
}

async function expectLoginForm(page: Page): Promise<void> {
  await expect(page).toHaveURL("/login");
  await expect(page.getByRole("heading", { name: "С возвращением", exact: true })).toBeVisible();
}

test("[INT-001] вход → reload → выход → защищённый URL снова требует входа", async ({
  page,
  accounts,
}) => {
  const account = await accounts.create();

  await test.step("Войти через форму", async () => {
    await page.goto("/login");
    await fillLoginForm(page, account);
    await authForm(page).submitLogin.click();
    await expectHome(page);
  });

  await test.step("Сессия в cookies переживает reload", async () => {
    await page.reload();
    await expectHome(page);
    const me = await page.request.get("/api/users/me");
    expect(me.status()).toBe(200);
    expect(await me.json()).toMatchObject({ username: account.username, email: account.email });
  });

  await test.step("Выйти из своего профиля", async () => {
    await page
      .getByRole("link", { name: `Открыть мой профиль @${account.username}`, exact: true })
      .click();
    await expect(page).toHaveURL(`/users/${account.username}`);
    await page
      .getByRole("button", { name: "Выйти", exact: true })
      .and(page.locator('[aria-haspopup="dialog"]'))
      .click();
    await page
      .getByRole("dialog", { name: "Выйти из Etch?", exact: true })
      .getByRole("button", { name: "Выйти", exact: true })
      .click();
    await expectLoginForm(page);
    await expect(page.getByText("Сессия истекла. Войдите снова.", { exact: true })).toBeHidden();
  });

  await test.step("Сервер завершил сессию: API и защищённый URL недоступны", async () => {
    await expect.poll(async () => (await page.request.get("/api/users/me")).status()).toBe(401);
    await page.goto("/settings");
    await expectLoginForm(page);
  });
});

test("[INT-002] регистрация в UI → автоматический вход → главная после reload", async ({
  page,
  accounts,
}) => {
  const account = accounts.reserve();
  const form = authForm(page);

  await test.step("Зарегистрироваться через форму", async () => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/login?mode=register");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await enterField(form.username, account.username, false);
    await enterField(form.email, account.email, false);
    await enterField(form.password, account.password, false);
    await form.submitRegistration.click();
    await expectHome(page);
    await expect(page.getByText("Здесь появятся ваши колоды", { exact: true })).toBeVisible();
  });

  await test.step("Сервер создал аккаунт с настройками по умолчанию", async () => {
    const me = await page.request.get("/api/users/me");
    expect(me.status()).toBe(200);
    expect(await me.json()).toMatchObject({
      username: account.username,
      email: account.email,
      settings: { theme: "light", show_previews_for_long: true },
    });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  await test.step("Новый пользователь остаётся в системе после reload", async () => {
    await page.reload();
    await expectHome(page);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });
});
