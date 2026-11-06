import { test, expect } from "../fixtures/mocked-test";
import {
  buildCurrentUser,
  buildEmptyHome,
  buildEmptyReviewSummary,
  buildReviewSession,
  buildReviewSummaryWithDueWords,
} from "../data/builders";
import { expectNoHorizontalOverflow } from "../helpers/layout";
import { mockOpenPracticeSession } from "../mocks/practice";

const SESSION_UUID = "01900000-0000-7000-8000-000000000501";

test.use({ currentUser: buildCurrentUser() });

test.beforeEach(async ({ api }) => {
  api.on("GET", "/bff/home", async ({ route }) => {
    await route.fulfill({ json: buildEmptyHome() });
  });
});

test(
  "[HOME-002] повторение слов на сегодня стартует с главной и открывает практику",
  { tag: ["@smoke", "@responsive"] },
  async ({ page, api }) => {
    const startRequests: unknown[] = [];

    await test.step("Подготовить два слова к повторению", async () => {
      api.on("GET", "/bff/reviews/summary", async ({ route }) => {
        await route.fulfill({ json: buildReviewSummaryWithDueWords() });
      });
      api.on("POST", "/bff/reviews/start", async ({ route, request }) => {
        startRequests.push(request.postDataJSON());
        await route.fulfill({ json: buildReviewSession(SESSION_UUID) });
      });
      mockOpenPracticeSession(api, SESSION_UUID, buildReviewSession(SESSION_UUID));
    });

    const widget = page.getByRole("region", { name: "Повторить сегодня", exact: true });

    await test.step("Открыть главную", async () => {
      await page.goto("/");
      await expect(widget.getByText("На сегодня всё", { exact: true })).toBeVisible();
      await expectNoHorizontalOverflow(page);
    });

    await test.step("Начать повторение направления «Перевод → слово»", async () => {
      await widget
        .getByRole("button", { name: "Повторить 2 слова: Перевод → слово", exact: true })
        .click();
    });

    await test.step("Проверить переход в сессию повторения", async () => {
      await expect(page).toHaveURL(`/practice?session=${SESSION_UUID}`);
      await expect(page.getByText("кот", { exact: true })).toBeVisible();
      expect(startRequests).toEqual([{ prompt_side: "front", words_per_session: 2 }]);
    });
  },
);

test("[HOME-003] слова уже повторены в другой вкладке → понятная ошибка и свежая сводка", async ({
  page,
  api,
  diagnostics,
}) => {
  // Слова повторены в другой вкладке: сервер узнаёт об этом при старте, дальше сводка пуста.
  // Число GET не проверяется: dev StrictMode монтирует эффект загрузки дважды.
  let wereWordsReviewedElsewhere = false;
  let summaryRequestsAfterStart = 0;

  await test.step("Сводка устаревает к моменту старта", async () => {
    api.on("GET", "/bff/reviews/summary", async ({ route }) => {
      if (wereWordsReviewedElsewhere) summaryRequestsAfterStart += 1;
      await route.fulfill({
        json: wereWordsReviewedElsewhere
          ? buildEmptyReviewSummary()
          : buildReviewSummaryWithDueWords(),
      });
    });
    api.on("POST", "/bff/reviews/start", async ({ route }) => {
      wereWordsReviewedElsewhere = true;
      await route.fulfill({
        status: 409,
        json: { code: "NO_CARDS_TO_REVIEW", message: "No cards are due for review today" },
      });
    });
    diagnostics.expectHttpError({
      method: "POST",
      pathname: "/api/bff/reviews/start",
      status: 409,
      reason: "Scenario reviews the words in another tab before this start",
    });
  });

  const widget = page.getByRole("region", { name: "Повторить сегодня", exact: true });

  await test.step("Нажать «Повторить» на устаревшей сводке", async () => {
    await page.goto("/");
    await widget
      .getByRole("button", { name: "Повторить 2 слова: Перевод → слово", exact: true })
      .click();
  });

  await test.step("Проверить сообщение и обновлённый список", async () => {
    await expect(widget.getByRole("alert")).toHaveText(
      "Слова на сегодня уже повторены — список обновлён.",
    );
    await expect(widget.getByText("Пока нечего повторять", { exact: true })).toBeVisible();
    await expect(page).toHaveURL("/");
    expect(summaryRequestsAfterStart).toBe(1);
  });
});
