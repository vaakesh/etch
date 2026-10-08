import { test, expect } from "../fixtures/mocked-test";
import type { Page, Request } from "@playwright/test";
import { buildCurrentUser } from "../data/builders";
import { activate } from "../helpers/actions";
import { expectNoHorizontalOverflow } from "../helpers/layout";
import { AUTH_ERRORS } from "../mocks/auth";
import { mockEmptyOwnProfile } from "../mocks/profile";

const USER = buildCurrentUser();
const PROFILE_URL = `/users/${USER.username}`;
const LOGOUT_PATH = "/api/auth/logout";

test.use({ currentUser: USER });

function isLogoutRequest(request: Request): boolean {
  return request.method() === "POST" && new URL(request.url()).pathname === LOGOUT_PATH;
}

function logoutControls(page: Page) {
  const dialog = page.getByRole("dialog", { name: "Выйти из Etch?", exact: true });
  return {
    // The page-level button; the dialog has its own confirm button with the same name.
    open: page
      .getByRole("button", { name: "Выйти", exact: true })
      .and(page.locator('[aria-haspopup="dialog"]')),
    dialog,
    confirm: dialog.getByRole("button", { name: "Выйти", exact: true }),
    cancel: dialog.getByRole("button", { name: "Остаться", exact: true }),
  };
}

async function openOwnProfile(page: Page): Promise<void> {
  await page.goto(PROFILE_URL);
  await expect(page.getByRole("heading", { name: `@${USER.username}`, exact: true })).toBeVisible();
}

async function expectLoginForm(page: Page): Promise<void> {
  await expect(page).toHaveURL("/login");
  await expect(page.getByRole("heading", { name: "С возвращением", exact: true })).toBeVisible();
}

test(
  "[AUTH-017] выход из профиля → форма входа, защищённые страницы недоступны",
  { tag: ["@smoke", "@responsive"] },
  async ({ page, api, auth, hasTouch }) => {
    mockEmptyOwnProfile(api, USER);
    auth.allowLogout();
    const controls = logoutControls(page);

    await test.step("Открыть диалог выхода в своём профиле", async () => {
      await openOwnProfile(page);
      await activate(controls.open, hasTouch);
      await expect(controls.dialog).toBeVisible();
      await expectNoHorizontalOverflow(page);
    });

    await test.step("Подтвердить выход", async () => {
      const logoutRequest = page.waitForRequest(isLogoutRequest);
      await activate(controls.confirm, hasTouch);
      await logoutRequest;
      await expectLoginForm(page);
    });

    await test.step("Прямой вход на защищённую страницу снова ведёт на вход", async () => {
      await page.goto(PROFILE_URL);
      await expectLoginForm(page);
    });
  },
);

test("[AUTH-018] отмена выхода → диалог закрыт, сессия сохранена", async ({ page, api }) => {
  // Logout is not mocked: a request after cancelling would fail the test.
  mockEmptyOwnProfile(api, USER);
  const controls = logoutControls(page);
  await openOwnProfile(page);

  await test.step("Закрыть диалог кнопкой «Остаться»", async () => {
    await controls.open.click();
    await expect(controls.cancel).toBeFocused();
    await controls.cancel.click();
    await expect(controls.dialog).toBeHidden();
    await expect(controls.open).toBeFocused();
  });

  await test.step("Закрыть диалог клавишей Escape", async () => {
    await controls.open.click();
    await expect(controls.dialog).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(controls.dialog).toBeHidden();
  });

  await test.step("Профиль открыт и после reload", async () => {
    await expect(page).toHaveURL(PROFILE_URL);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: `@${USER.username}`, exact: true }),
    ).toBeVisible();
  });
});

test("[AUTH-019] сервер не подтвердил выход → локальная сессия всё равно завершена", async ({
  page,
  api,
  diagnostics,
}) => {
  mockEmptyOwnProfile(api, USER);
  api.on("POST", "/auth/logout", async ({ route }) => {
    await route.fulfill(AUTH_ERRORS.internal);
  });
  diagnostics.expectHttpError({
    method: "POST",
    pathname: LOGOUT_PATH,
    status: 500,
    reason: "Scenario fails the server-side logout",
  });
  const controls = logoutControls(page);

  await openOwnProfile(page);
  await controls.open.click();
  const logoutResponse = page.waitForResponse((response) => isLogoutRequest(response.request()));
  await controls.confirm.click();
  await logoutResponse;

  await expectLoginForm(page);
  await expect(page.getByRole("alert")).toBeHidden();
});

test("[AUTH-021] добровольный выход → нет уведомления об истёкшей сессии", async ({
  page,
  api,
  auth,
}) => {
  mockEmptyOwnProfile(api, USER);
  auth.allowLogout();
  const controls = logoutControls(page);

  await openOwnProfile(page);
  await controls.open.click();
  await controls.confirm.click();

  await expectLoginForm(page);
  await expect(page.getByText("Сессия истекла. Войдите снова.", { exact: true })).toBeHidden();
});

test("[AUTH-022] сервер отклонил сессию при переходе → вход с уведомлением об истечении", async ({
  page,
  api,
  auth,
  diagnostics,
}) => {
  mockEmptyOwnProfile(api, USER);
  api.on("GET", "/bff/home", async ({ route }) => {
    await route.fulfill({
      status: 401,
      json: { code: "ACCESS_TOKEN_NOT_FOUND", message: "Access token not found" },
    });
  });
  diagnostics.expectHttpError({
    method: "GET",
    pathname: "/api/bff/home",
    status: 401,
    reason: "Scenario ends the session on the server before the next protected request",
  });

  await test.step("Сессия пропадает на сервере, пока открыт профиль", async () => {
    await openOwnProfile(page);
    auth.signOut();
  });

  await test.step("Переход на главную без действий выхода", async () => {
    await page
      .getByRole("navigation", { name: "Основная навигация", exact: true })
      .getByRole("link", { name: "Главная", exact: true })
      .click();
  });

  await test.step("Показан вход с объяснением причины", async () => {
    await expectLoginForm(page);
    await expect(page.getByRole("status")).toHaveText("Сессия истекла. Войдите снова.");
  });
});

test("[AUTH-020] ответ на выход задерживается → вход показан сразу, запрос один", async ({
  page,
  api,
  auth,
}) => {
  mockEmptyOwnProfile(api, USER);
  const gate = api.gate();
  auth.allowLogout({ holdUntil: gate.opened });
  const logoutRequests: Request[] = [];
  page.on("request", (request) => {
    if (isLogoutRequest(request)) logoutRequests.push(request);
  });
  const controls = logoutControls(page);

  await openOwnProfile(page);
  await controls.open.click();
  const logoutRequest = page.waitForRequest(isLogoutRequest);
  await controls.confirm.click();
  await logoutRequest;

  // Local logout is immediate: the guard leaves the protected page before the server answers.
  await expectLoginForm(page);
  gate.open();
  await expect(page).toHaveURL("/login");
  expect(logoutRequests).toHaveLength(1);
});
