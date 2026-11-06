import { test, expect } from "../fixtures/mocked-test";
import type { Page } from "@playwright/test";
import {
  buildCurrentUser,
  buildFirstCorrectAnswer,
  buildRateAnswerResponse,
  buildReviewSession,
} from "../data/builders";
import type { ApiMockRouter } from "../mocks/api-router";
import { mockOpenPracticeSession } from "../mocks/practice";

const SESSION_UUID = "01900000-0000-7000-8000-000000000501";
const STARTED_AT = new Date("2026-11-06T09:00:00Z");
// PRACTICE_RATING_ADVANCE_DELAY_MS in src/features/practice/model/practice-rating-flow.ts.
const RATING_ADVANCE_DELAY_MS = 900;

test.use({ currentUser: buildCurrentUser() });

/** The first card «кот» answered correctly; rating requests are collected in `ratings`. */
function mockAnsweredFirstCard(api: ApiMockRouter, ratings: unknown[]): void {
  mockOpenPracticeSession(api, SESSION_UUID, buildReviewSession(SESSION_UUID));
  api.on("PUT", `/training-sessions/${SESSION_UUID}/items/1/submit`, async ({ route }) => {
    await route.fulfill({ json: buildFirstCorrectAnswer("cat") });
  });
  api.on("PUT", `/training-sessions/${SESSION_UUID}/items/1/rating`, async ({ route, request }) => {
    const body: unknown = request.postDataJSON();
    ratings.push(body);
    await route.fulfill({ json: buildRateAnswerResponse(3) });
  });
}

/**
 * Answers the first card and pauses the clock on the rating: from then on the rating animation
 * moves only by `clock.runFor`. The clock runs during loading, the lazy page needs its timers.
 */
async function answerFirstCard(page: Page): Promise<void> {
  await page.clock.install({ time: STARTED_AT });
  await page.goto(`/practice?session=${SESSION_UUID}`);

  await expect(page.getByRole("heading", { name: "кот", exact: true })).toBeVisible();
  await expect(page.getByLabel("Ваш ответ", { exact: true })).toBeFocused();
  await page.keyboard.type("cat");
  await page.keyboard.press("Enter");

  await expect(page.getByText("Верно", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Оцените ответ", { exact: true })).toBeFocused();
  const now = await page.evaluate(() => Date.now());
  await page.clock.pauseAt(now + 1_000);
}

test(
  "[PRACTICE-001] ответ → цифра оценки → Enter сразу открывает следующее слово",
  { tag: ["@smoke"] },
  async ({ page, api }) => {
    const ratings: unknown[] = [];

    await test.step("Подготовить сессию из двух слов", async () => {
      mockAnsweredFirstCard(api, ratings);
    });

    await test.step("Ответить на первое слово с клавиатуры", async () => {
      await answerFirstCard(page);
    });

    const rating = page.getByRole("group", { name: "Оценка ответа", exact: true });

    await test.step("Ввести 3 в то же поле, не переводя фокус", async () => {
      // До сохранения оценки срок следующего повторения неизвестен
      await expect(page.getByText(/^Повторим/)).toHaveCount(0);
      await page.keyboard.press("3");
      await expect(
        rating.getByRole("button", { name: "Хорошо Вспомнил, подумав" }),
      ).toHaveAttribute("aria-pressed", "true");
      await expect(page.getByText("Enter — сразу дальше", { exact: true })).toBeVisible();
      await expect.poll(() => ratings).toEqual([{ rating: 3 }]);
      // next_review_at из buildRateAnswerResponse — через 3 дня после ответа
      await expect(page.getByText("Повторим через 3 дня", { exact: true })).toBeVisible();
    });

    await test.step("Пропустить анимацию повторным Enter", async () => {
      await page.keyboard.press("Enter");
      await expect(page.getByRole("heading", { name: "пёс", exact: true })).toBeVisible();
      await expect(page.getByLabel("Ваш ответ", { exact: true })).toBeFocused();
      expect(ratings).toEqual([{ rating: 3 }]);
    });
  },
);

test("[PRACTICE-002] оценка без Enter → следующее слово после анимации", async ({ page, api }) => {
  const ratings: unknown[] = [];

  await test.step("Ответить на первое слово и выбрать оценку", async () => {
    mockAnsweredFirstCard(api, ratings);
    await answerFirstCard(page);
    await page.keyboard.press("3");
    await expect.poll(() => ratings).toEqual([{ rating: 3 }]);
  });

  await test.step("Дождаться конца анимации", async () => {
    await page.clock.runFor(RATING_ADVANCE_DELAY_MS - 100);
    await expect(page.getByRole("heading", { name: "кот", exact: true })).toBeVisible();
    await page.clock.runFor(100);
    await expect(page.getByRole("heading", { name: "пёс", exact: true })).toBeVisible();
  });
});

test("[PRACTICE-003] Enter без цифры → следующее слово без оценки", async ({ page, api }) => {
  const ratings: unknown[] = [];

  await test.step("Ответить на первое слово", async () => {
    mockAnsweredFirstCard(api, ratings);
    await answerFirstCard(page);
  });

  await test.step("Нажать Enter, не выбирая оценку", async () => {
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "пёс", exact: true })).toBeVisible();
    expect(ratings).toEqual([]);
  });
});
