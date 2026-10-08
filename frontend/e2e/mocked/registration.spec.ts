import { test, expect } from "../fixtures/mocked-test";
import type { Page, Request } from "@playwright/test";
import { buildCurrentUser } from "../data/builders";
import { activate } from "../helpers/actions";
import { authForm, enterField } from "../helpers/auth-form";
import { expectNoHorizontalOverflow } from "../helpers/layout";
import { AUTH_ERRORS } from "../mocks/auth";
import { mockEmptyHome } from "../mocks/home";

const USER = buildCurrentUser();
const ACCOUNT = { username: USER.username, email: USER.email, password: "correct-horse-1" };
const CREATE_PATH = "/api/users/create";
const LOGIN_PATH = "/api/auth/login";

function isPost(pathname: string): (request: Request) => boolean {
  return (request) => request.method() === "POST" && new URL(request.url()).pathname === pathname;
}

async function fillRegistration(page: Page, hasTouch = false): Promise<void> {
  const form = authForm(page);
  await enterField(form.username, ACCOUNT.username, hasTouch);
  await enterField(form.email, ACCOUNT.email, hasTouch);
  await enterField(form.password, ACCOUNT.password, hasTouch);
}

test(
  "[AUTH-013] регистрация → аккаунт создан, автоматический вход, главная",
  { tag: ["@smoke", "@responsive"] },
  async ({ page, api, auth, hasTouch }) => {
    auth.allowRegistration(USER);
    mockEmptyHome(api);
    const form = authForm(page);

    await test.step("Открыть регистрацию по прямой ссылке и заполнить форму", async () => {
      await page.goto("/login?mode=register");
      await expect(
        page.getByRole("heading", { name: "Начните с Etch", exact: true }),
      ).toBeVisible();
      await fillRegistration(page, hasTouch);
      await expectNoHorizontalOverflow(page);
    });

    await test.step("Отправить: создание аккаунта, затем вход теми же данными", async () => {
      const createRequest = page.waitForRequest(isPost(CREATE_PATH));
      const loginRequest = page.waitForRequest(isPost(LOGIN_PATH));
      await activate(form.submitRegistration, hasTouch);
      expect((await createRequest).postDataJSON()).toEqual(ACCOUNT);
      expect((await loginRequest).postDataJSON()).toEqual({
        username: ACCOUNT.username,
        password: ACCOUNT.password,
      });
    });

    await test.step("Открыта главная нового пользователя", async () => {
      await expect(page).toHaveURL("/");
      await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
    });
  },
);

test("[AUTH-014] занятое имя → конфликт, вход не выполняется, поля сохранены", async ({
  page,
  api,
  diagnostics,
}) => {
  // Login is not mocked: an automatic sign-in after a failed registration would fail the test.
  api.on("POST", "/users/create", async ({ route }) => {
    await route.fulfill(AUTH_ERRORS.usernameAlreadyExists);
  });
  diagnostics.expectHttpError({
    method: "POST",
    pathname: CREATE_PATH,
    status: 409,
    reason: "Scenario answers registration with USERNAME_ALREADY_EXISTS",
  });
  const form = authForm(page);

  await page.goto("/login?mode=register");
  await fillRegistration(page);
  await form.submitRegistration.click();

  await expect(form.error).toHaveText("Пользователь с таким именем или email уже существует.");
  await expect(page.getByRole("heading", { name: "Начните с Etch", exact: true })).toBeVisible();
  await expect(form.username).toHaveAttribute("aria-invalid", "true");
  await expect(form.username).toHaveValue(ACCOUNT.username);
  await expect(form.email).toHaveValue(ACCOUNT.email);
  await expect(form.password).toHaveValue(ACCOUNT.password);
  await expect(form.submitRegistration).toBeEnabled();
});

test("[AUTH-015] аккаунт создан, но вход не удался → форма входа с подсказкой", async ({
  page,
  api,
  auth,
  diagnostics,
}) => {
  auth.allowRegistration(USER, { enableLogin: false });
  api.on("POST", "/auth/login", async ({ route }) => {
    await route.fulfill(AUTH_ERRORS.internal);
  });
  diagnostics.expectHttpError({
    method: "POST",
    pathname: LOGIN_PATH,
    status: 500,
    reason: "Scenario fails the automatic sign-in after a successful registration",
  });
  mockEmptyHome(api);
  const form = authForm(page);

  await test.step("Зарегистрироваться при сбое автоматического входа", async () => {
    await page.goto("/login?mode=register");
    await fillRegistration(page);
    await form.submitRegistration.click();
  });

  await test.step("Показан режим входа: аккаунт уже существует", async () => {
    await expect(form.error).toHaveText(
      "Аккаунт создан, но войти автоматически не удалось. Попробуйте войти.",
    );
    await expect(page.getByRole("heading", { name: "С возвращением", exact: true })).toBeVisible();
    await expect(form.loginMode).toHaveAttribute("aria-pressed", "true");
    await expect(form.email).toBeHidden();
    await expect(form.username).toHaveValue(ACCOUNT.username);
    await expect(form.password).toHaveValue(ACCOUNT.password);
  });

  await test.step("Вход созданным аккаунтом удаётся без повторной регистрации", async () => {
    auth.allowLogin({ username: ACCOUNT.username, password: ACCOUNT.password }, USER);
    api.on("POST", "/users/create", async ({ route }) => {
      api.unexpected.push("POST /api/users/create (account already created)");
      await route.abort("blockedbyclient");
    });
    await form.submitLogin.click();
    await expect(page).toHaveURL("/");
    await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
  });
});

test("[AUTH-016] пустой email → регистрация не отправляет запрос", async ({ page }) => {
  // Neither registration nor login is mocked: any request would fail the test.
  const createRequests: Request[] = [];
  page.on("request", (request) => {
    if (isPost(CREATE_PATH)(request)) createRequests.push(request);
  });
  const form = authForm(page);

  await page.goto("/login?mode=register");
  await enterField(form.username, ACCOUNT.username, false);
  await enterField(form.password, ACCOUNT.password, false);
  await form.submitRegistration.click();

  await expect
    .poll(() => form.email.evaluate((input: HTMLInputElement) => input.validity.valueMissing))
    .toBe(true);
  await expect(form.submitRegistration).toBeEnabled();
  await expect(page).toHaveURL("/login?mode=register");
  expect(createRequests).toHaveLength(0);
});
