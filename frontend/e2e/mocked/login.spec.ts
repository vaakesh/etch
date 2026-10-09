import { test, expect } from "../fixtures/mocked-test";
import type { Page, Request } from "@playwright/test";
import { buildCurrentUser } from "../data/builders";
import { activate } from "../helpers/actions";
import { authForm, enterField, fillLoginForm } from "../helpers/auth-form";
import { expectNoHorizontalOverflow } from "../helpers/layout";
import { AUTH_ERRORS } from "../mocks/auth";
import { mockEmptyHome } from "../mocks/home";

const CREDENTIALS = { username: "e2e_student", password: "correct-horse-1" };
const LOGIN_PATH = "/api/auth/login";

function isLoginRequest(request: Request): boolean {
  return request.method() === "POST" && new URL(request.url()).pathname === LOGIN_PATH;
}

function collectLoginRequests(page: Page): Request[] {
  const requests: Request[] = [];
  page.on("request", (request) => {
    if (isLoginRequest(request)) requests.push(request);
  });
  return requests;
}

async function openLoginAndFill(
  page: Page,
  credentials = CREDENTIALS,
  hasTouch = false,
): Promise<void> {
  await page.goto("/login");
  await fillLoginForm(page, credentials, hasTouch);
}

test.describe("гость на форме входа", () => {
  test(
    "[AUTH-003] верные данные → главная, сессия переживает reload",
    { tag: ["@smoke", "@responsive"] },
    async ({ page, api, auth, hasTouch }) => {
      auth.allowLogin(CREDENTIALS, buildCurrentUser());
      mockEmptyHome(api);
      const form = authForm(page);

      await test.step("Ввести данные и отправить форму", async () => {
        await openLoginAndFill(page, CREDENTIALS, hasTouch);
        const loginRequest = page.waitForRequest(isLoginRequest);
        await activate(form.submitLogin, hasTouch);
        expect((await loginRequest).postDataJSON()).toEqual(CREDENTIALS);
      });

      await test.step("Открыта защищённая главная", async () => {
        await expect(page).toHaveURL("/");
        await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
        await expectNoHorizontalOverflow(page);
      });

      await test.step("После reload сессия сохраняется", async () => {
        await page.reload();
        await expect(page).toHaveURL("/");
        await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
      });
    },
  );

  test("[AUTH-004] неверный пароль → ошибка, поля сохранены, повтор успешен", async ({
    page,
    api,
    auth,
    diagnostics,
  }) => {
    auth.allowLogin(CREDENTIALS, buildCurrentUser());
    mockEmptyHome(api);
    diagnostics.expectHttpError({
      method: "POST",
      pathname: LOGIN_PATH,
      status: 404,
      reason: "Backend answers unknown credentials with INVALID_LOGIN_CREDENTIALS",
    });
    const form = authForm(page);

    await test.step("Отправить неверный пароль", async () => {
      await openLoginAndFill(page, { ...CREDENTIALS, password: "wrong-horse-1" });
      await form.submitLogin.click();
      await expect(form.error).toHaveText("Неверное имя пользователя или пароль.");
      await expect(page).toHaveURL("/login");
    });

    await test.step("Поля помечены и не очищены", async () => {
      await expect(form.username).toHaveAttribute("aria-invalid", "true");
      await expect(form.password).toHaveAttribute("aria-invalid", "true");
      await expect(form.username).toHaveValue(CREDENTIALS.username);
      await expect(form.password).toHaveValue("wrong-horse-1");
    });

    await test.step("Исправить пароль и войти", async () => {
      await form.password.fill(CREDENTIALS.password);
      await form.submitLogin.click();
      await expect(page).toHaveURL("/");
      await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
    });
  });

  test("[AUTH-005] пустой пароль → форма не отправляет запрос", async ({ page }) => {
    // No login handler: a request would also fail the test as an unexpected API call.
    const loginRequests = collectLoginRequests(page);
    const form = authForm(page);
    await page.goto("/login");
    await enterField(form.username, CREDENTIALS.username, false);
    await form.submitLogin.click();

    await expect
      .poll(() => form.password.evaluate((input: HTMLInputElement) => input.validity.valueMissing))
      .toBe(true);
    await expect(form.submitLogin).toBeEnabled();
    await expect(page).toHaveURL("/login");
    expect(loginRequests).toHaveLength(0);
  });

  test("[AUTH-006] сетевой сбой → сообщение о связи, повтор успешен", async ({
    page,
    api,
    auth,
    diagnostics,
  }) => {
    api.on("POST", "/auth/login", async ({ route }) => {
      await route.abort("failed");
    });
    diagnostics.expectRequestFailure({
      method: "POST",
      pathname: LOGIN_PATH,
      reason: "Scenario drops the login request at the transport level",
    });
    mockEmptyHome(api);
    const form = authForm(page);

    await test.step("Отправить форму при недоступном сервере", async () => {
      await openLoginAndFill(page);
      await form.submitLogin.click();
      await expect(form.error).toHaveText("Не удалось связаться с сервером. Попробуйте ещё раз.");
      await expect(form.username).not.toHaveAttribute("aria-invalid");
      await expect(form.username).toHaveValue(CREDENTIALS.username);
      await expect(form.password).toHaveValue(CREDENTIALS.password);
    });

    await test.step("Сервер снова доступен: повторная отправка без повторного ввода", async () => {
      auth.allowLogin(CREDENTIALS, buildCurrentUser());
      await form.submitLogin.click();
      await expect(page).toHaveURL("/");
      await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
    });
  });

  const serverErrors = [
    {
      id: "AUTH-007",
      title: "422 от сервера → сообщение о формате полей",
      response: AUTH_ERRORS.validation,
      message:
        "Имя пользователя — 3–18 символов: латинские буквы, цифры, _ или -, пароль — 8–128 символов без пробелов.",
      invalidFields: true,
    },
    {
      id: "AUTH-008",
      title: "429 от сервера → общая ошибка входа",
      response: AUTH_ERRORS.rateLimit,
      message: "Не удалось войти. Попробуйте ещё раз.",
      invalidFields: false,
    },
    {
      id: "AUTH-009",
      title: "500 от сервера → общая ошибка входа",
      response: AUTH_ERRORS.internal,
      message: "Не удалось войти. Попробуйте ещё раз.",
      invalidFields: false,
    },
    {
      id: "AUTH-023",
      title: "403 CAPTCHA_INVALID → сообщение о проверке от ботов",
      response: AUTH_ERRORS.captchaInvalid,
      message: "Не удалось пройти проверку от ботов. Попробуйте ещё раз.",
      invalidFields: false,
    },
  ];

  for (const { id, title, response, message, invalidFields } of serverErrors) {
    test(`[${id}] ${title}`, async ({ page, api, diagnostics }) => {
      api.on("POST", "/auth/login", async ({ route }) => {
        await route.fulfill(response);
      });
      diagnostics.expectHttpError({
        method: "POST",
        pathname: LOGIN_PATH,
        status: response.status,
        reason: `Scenario answers login with ${response.json.code}`,
      });
      const form = authForm(page);

      await openLoginAndFill(page);
      await form.submitLogin.click();

      await expect(form.error).toHaveText(message);
      if (invalidFields) await expect(form.username).toHaveAttribute("aria-invalid", "true");
      else await expect(form.username).not.toHaveAttribute("aria-invalid");
      await expect(page).toHaveURL("/login");
      await expect(form.submitLogin).toBeEnabled();
      await expect(form.username).toHaveValue(CREDENTIALS.username);
    });
  }

  test("[AUTH-010] ответ задерживается → форма заблокирована, отправка одна", async ({
    page,
    api,
    auth,
  }) => {
    const gate = api.gate();
    auth.allowLogin(CREDENTIALS, buildCurrentUser(), { holdUntil: gate.opened });
    mockEmptyHome(api);
    const loginRequests = collectLoginRequests(page);
    const form = authForm(page);

    await test.step("Отправить форму: запрос получен, ответа ещё нет", async () => {
      await openLoginAndFill(page);
      const loginRequest = page.waitForRequest(isLoginRequest);
      await form.submitLogin.click();
      await loginRequest;
    });

    await test.step("Форма показывает ожидание и не принимает ввод", async () => {
      const pending = page.getByRole("button", { name: "Входим…", exact: true });
      await expect(pending).toBeDisabled();
      await expect(form.username).toBeDisabled();
      await expect(form.password).toBeDisabled();
      await expect(form.registerMode).toBeDisabled();
      await expect(page).toHaveURL("/login");
    });

    await test.step("После ответа открыта главная, запрос был один", async () => {
      gate.open();
      await expect(page).toHaveURL("/");
      await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
      expect(loginRequests).toHaveLength(1);
    });
  });

  test("[AUTH-011] deep link без сессии → после входа открыт запрошенный раздел", async ({
    page,
    auth,
  }) => {
    // The home BFF is not mocked: landing on "/" instead of the deep link would fail the test.
    auth.allowLogin(CREDENTIALS, buildCurrentUser());
    const form = authForm(page);

    await test.step("Открыть защищённые настройки без сессии", async () => {
      await page.goto("/settings");
      await expect(page).toHaveURL("/login");
      await expect(form.submitLogin).toBeVisible();
      // A guest never had a session: nothing expired.
      await expect(page.getByText("Сессия истекла. Войдите снова.", { exact: true })).toBeHidden();
    });

    await test.step("Войти", async () => {
      await fillLoginForm(page, CREDENTIALS);
      await form.submitLogin.click();
    });

    await test.step("Открыты настройки, а не главная", async () => {
      await expect(page).toHaveURL("/settings");
      await expect(page.getByRole("heading", { name: "Настройки", exact: true })).toBeVisible();
    });
  });
});

test.describe("авторизованный пользователь", () => {
  test.use({ currentUser: buildCurrentUser() });

  test("[AUTH-012] открывает /login → перенаправлен на главную", async ({ page, api }) => {
    mockEmptyHome(api);
    await page.goto("/login");
    await expect(page).toHaveURL("/");
    await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
  });
});
