import type { Page } from "@playwright/test";
import { test, expect } from "../fixtures/mocked-test";
import { buildCurrentUser, buildEmptyCursorPage } from "../data/builders";
import { mockEmptyHome } from "../mocks/home";
import { expectNoHorizontalOverflow } from "../helpers/layout";

async function openHome(page: Page) {
  await page.goto("/");
  await expect(
    page.getByText(/^(Здесь появятся ваши колоды|Your decks will appear here)$/),
  ).toBeVisible();
}

test.use({ currentUser: buildCurrentUser() });
test.beforeEach(async ({ api }) => mockEmptyHome(api));

test("[ASK-001] sends one question, shows loading and keeps the answer when closed", async ({
  page,
  api,
}, testInfo) => {
  const gate = api.gate();
  const requests: unknown[] = [];
  api.on("POST", "/ask", async ({ route, request }) => {
    requests.push(request.postDataJSON());
    await gate.opened;
    await route.fulfill({
      json: {
        text: "Откройте библиотеку и выберите импорт карточек.\nПодготовьте файл с вопросами и ответами.",
      },
    });
  });
  await openHome(page);
  await expect(page.getByRole("heading", { name: "Главная", exact: true })).toBeVisible();
  const launcher = page.getByRole("button", { name: "Открыть помощника Etch" });
  await launcher.click();
  const dialog = page.getByRole("dialog", { name: "Помощник Etch" });
  const input = dialog.getByRole("textbox", { name: "Ваш вопрос" });
  const send = dialog.getByRole("button", { name: "Отправить вопрос" });
  await expect(input).toBeFocused();
  await expect(send).toBeDisabled();
  await page.screenshot({
    path: testInfo.outputPath("assistant-light-empty.png"),
    animations: "disabled",
  });
  await dialog.getByRole("button", { name: "Как импортировать карточки?", exact: true }).click();
  await expect(input).toHaveValue("Как импортировать карточки?");
  expect(requests).toEqual([]);
  await input.press("Enter");
  await expect(dialog.getByRole("status")).toHaveText("Готовлю ответ…");
  await expect(send).toBeDisabled();
  await input.press("Enter");
  await expect.poll(() => requests.length).toBe(1);
  await page.screenshot({
    path: testInfo.outputPath("assistant-light-loading.png"),
    animations: "disabled",
  });
  await dialog.getByRole("button", { name: "Закрыть помощника Etch" }).click();
  await expect(dialog).toBeHidden();
  gate.open();
  await launcher.click();
  await expect(dialog.getByRole("log")).toContainText(
    "Откройте библиотеку и выберите импорт карточек.",
  );
  await expect(dialog.getByRole("status")).toHaveCount(0);
  expect(requests).toEqual([{ message: "Как импортировать карточки?" }]);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: testInfo.outputPath("assistant-light-answer.png"),
    animations: "disabled",
  });
});

const errors = [
  { status: 429, code: "RATE_LIMIT_EXCEEDED", text: "Лимит вопросов исчерпан. Попробуйте позже." },
  {
    status: 503,
    code: "RAG_UNAVAILABLE",
    text: "Помощник сейчас недоступен. Попробуйте чуть позже.",
  },
  {
    status: 504,
    code: "RAG_TIMEOUT",
    text: "Ответ занял слишком много времени. Попробуйте позже.",
  },
  {
    status: 502,
    code: "RAG_BAD_RESPONSE",
    text: "Не удалось получить ответ. Попробуйте ещё раз позже.",
  },
  {
    status: 200,
    code: "INVALID_ASK_RESPONSE",
    text: "Не удалось получить ответ. Попробуйте ещё раз позже.",
  },
] as const;

for (const scenario of errors) {
  test(`[ASK-002] handles ${scenario.code} and preserves the question`, async ({
    page,
    api,
    diagnostics,
  }) => {
    let requests = 0;
    if (scenario.status >= 400)
      diagnostics.expectHttpError({
        method: "POST",
        pathname: "/api/ask",
        status: scenario.status,
        reason: "Assistant error scenario",
      });
    api.on("POST", "/ask", async ({ route }) => {
      requests++;
      await route.fulfill({
        status: scenario.status,
        json: { code: scenario.code, message: "private-provider-details" },
      });
    });
    await openHome(page);
    await page.getByRole("button", { name: "Открыть помощника Etch" }).click();
    const dialog = page.getByRole("dialog", { name: "Помощник Etch" });
    const input = dialog.getByRole("textbox", { name: "Ваш вопрос" });
    await input.fill("Как начать практику?");
    await dialog.getByRole("button", { name: "Отправить вопрос" }).click();
    await expect(dialog.getByRole("alert")).toHaveText(scenario.text);
    await expect(input).toHaveValue("Как начать практику?");
    await expect(dialog.getByRole("button", { name: "Отправить вопрос" })).toBeEnabled();
    await expect(dialog).not.toContainText("private-provider-details");
    expect(requests).toBe(1);
  });
}

test("[ASK-003] enforces question length and restores focus after Escape", async ({
  page,
  api,
}) => {
  api.on("POST", "/ask", async ({ route, request }) => {
    expect(request.postDataJSON()).toEqual({ message: "😀".repeat(200) });
    await route.fulfill({ json: { text: "Ответ" } });
  });
  await openHome(page);
  const launcher = page.getByRole("button", { name: "Открыть помощника Etch" });
  await launcher.click();
  const dialog = page.getByRole("dialog", { name: "Помощник Etch" });
  const input = dialog.getByRole("textbox", { name: "Ваш вопрос" });
  await input.fill("   ");
  await expect(dialog.getByRole("button", { name: "Отправить вопрос" })).toBeDisabled();
  await input.fill("😀".repeat(201));
  await expect(input).toHaveValue("😀".repeat(200));
  await expect(dialog.getByText("200 / 200", { exact: true })).toBeVisible();
  await input.press("Enter");
  await expect(dialog.getByRole("log")).toContainText("Ответ");
  await input.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(launcher).toBeFocused();
});

test("[ASK-004] hides the chat below the desktop breakpoint", async ({ page }) => {
  await openHome(page);
  const launcher = page.getByRole("button", {
    name: "Открыть помощника Etch",
    includeHidden: true,
  });
  await page.setViewportSize({ width: 1023, height: 768 });
  await expect(launcher).toBeHidden();
  await page.setViewportSize({ width: 1024, height: 768 });
  await expect(launcher).toBeVisible();
  await launcher.click();
  const dialog = page.getByRole("dialog", { name: "Помощник Etch" });
  await expect(dialog).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(launcher).toBeHidden();
  await expect(dialog).toBeHidden();
  await expectNoHorizontalOverflow(page);
  await page.setViewportSize({ width: 1025, height: 768 });
  await expect(launcher).toBeVisible();
});

test("[ASK-005] reports a network failure without an automatic retry", async ({
  page,
  api,
  diagnostics,
}) => {
  let requests = 0;
  diagnostics.expectRequestFailure({
    method: "POST",
    pathname: "/api/ask",
    reason: "Intentional assistant network failure",
  });
  api.on("POST", "/ask", async ({ route }) => {
    requests++;
    await route.abort("connectionfailed");
  });
  await openHome(page);
  await page.getByRole("button", { name: "Открыть помощника Etch" }).click();
  const dialog = page.getByRole("dialog", { name: "Помощник Etch" });
  await dialog.getByRole("textbox", { name: "Ваш вопрос" }).fill("Как начать практику?");
  await dialog.getByRole("button", { name: "Отправить вопрос" }).click();
  await expect(dialog.getByRole("alert")).toHaveText(
    "Нет связи с сервером. Проверьте подключение.",
  );
  expect(requests).toBe(1);
});

test.describe("English dark theme", () => {
  const user = buildCurrentUser();
  user.settings = { ...user.settings, locale: "en-US", theme: "dark" };
  test.use({ currentUser: user });

  test("[ASK-006] renders a long answer as plain text in the dark theme", async ({
    page,
    api,
  }, testInfo) => {
    const answer =
      "<script>alert('unsafe')</script>\n" + "Use decks to organize your cards. ".repeat(50);
    api.on("POST", "/ask", async ({ route }) => {
      await route.fulfill({ json: { text: answer } });
    });
    await openHome(page);
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.getByRole("button", { name: "Open Etch assistant" }).click();
    const dialog = page.getByRole("dialog", { name: "Etch assistant" });
    await dialog.getByRole("textbox", { name: "Your question" }).fill("How do I create a deck?");
    await dialog.getByRole("button", { name: "Send question" }).click();
    await expect(dialog.getByRole("log")).toContainText("<script>alert('unsafe')</script>");
    await expect(dialog.locator("script")).toHaveCount(0);
    await expect(dialog.getByRole("textbox")).toBeVisible();
    const answerBox = await dialog.locator('[data-role="assistant"]').boundingBox();
    const headerBox = await dialog.locator("header").boundingBox();
    expect(answerBox).not.toBeNull();
    expect(headerBox).not.toBeNull();
    if (answerBox && headerBox)
      expect(answerBox.y).toBeGreaterThanOrEqual(headerBox.y + headerBox.height);
    await expectNoHorizontalOverflow(page);
    await page.screenshot({
      path: testInfo.outputPath("assistant-dark-answer.png"),
      animations: "disabled",
    });
  });
});

test("[ASK-007] keeps the conversation after navigating to the library", async ({
  page,
  api,
}, testInfo) => {
  api.on("POST", "/ask", async ({ route }) => {
    await route.fulfill({ json: { text: "Откройте библиотеку, чтобы посмотреть свои колоды." } });
  });
  api.on("GET", "/bff/library/decks", async ({ route }) => {
    await route.fulfill({ json: buildEmptyCursorPage() });
  });
  await openHome(page);
  const launcher = page.getByRole("button", { name: "Открыть помощника Etch" });
  await launcher.click();
  const dialog = page.getByRole("dialog", { name: "Помощник Etch" });
  await dialog.getByRole("textbox", { name: "Ваш вопрос" }).fill("Где мои колоды?");
  await dialog.getByRole("button", { name: "Отправить вопрос" }).click();
  await expect(dialog.getByRole("log")).toContainText("Откройте библиотеку");
  await dialog.getByRole("button", { name: "Закрыть помощника Etch" }).click();
  await page.getByRole("link", { name: "Библиотека", exact: true }).click();
  await expect(page).toHaveURL("/library/decks");
  await expect(page.getByRole("heading", { name: "Библиотека", exact: true })).toBeVisible();
  await launcher.click();
  await expect(dialog.getByRole("log")).toContainText("Где мои колоды?");
  await expect(dialog.getByRole("log")).toContainText("Откройте библиотеку");
  await page.screenshot({
    path: testInfo.outputPath("assistant-library.png"),
    animations: "disabled",
  });
});
