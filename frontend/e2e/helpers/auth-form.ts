import type { Locator, Page } from "@playwright/test";
import { activate } from "./actions";

/**
 * Login fields stay read-only until the user focuses one (autofill guard in LoginPage), so a
 * value is entered the way a person does it: activate the field first, then type.
 */
export async function enterField(field: Locator, value: string, hasTouch: boolean): Promise<void> {
  await activate(field, hasTouch);
  await field.fill(value);
}

export async function fillLoginForm(
  page: Page,
  credentials: { username: string; password: string },
  hasTouch = false,
): Promise<void> {
  const form = authForm(page);
  await enterField(form.username, credentials.username, hasTouch);
  await enterField(form.password, credentials.password, hasTouch);
}

// ru-RU labels of src/pages/LoginPage; specs pin the locale through the project config.
export function authForm(page: Page) {
  return {
    username: page.getByRole("textbox", { name: "Имя пользователя", exact: true }),
    email: page.getByRole("textbox", { name: "Email", exact: true }),
    // A password input has no ARIA role; its label also carries the required mark.
    password: page.getByLabel("Пароль"),
    loginMode: page.getByRole("button", { name: "Вход", exact: true }),
    registerMode: page.getByRole("button", { name: "Регистрация", exact: true }),
    submitLogin: page.getByRole("button", { name: "Войти", exact: true }),
    submitRegistration: page.getByRole("button", { name: "Создать аккаунт", exact: true }),
    error: page.getByRole("alert"),
  };
}
