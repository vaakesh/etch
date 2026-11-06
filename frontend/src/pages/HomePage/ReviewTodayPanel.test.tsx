import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api";
import type {
  ReviewStartState,
  ReviewSummaryState,
} from "../../features/reviews/model/useReviewToday";
import { LocaleProvider, type AppLocale } from "../../i18n";

const hookState = vi.hoisted(() => ({
  summary: { status: "loading" } as ReviewSummaryState,
  startState: { status: "idle" } as ReviewStartState,
}));

vi.mock("../../features/reviews/model/useReviewToday", () => ({
  useReviewToday: () => ({
    summary: hookState.summary,
    startState: hookState.startState,
    retry: vi.fn(),
    start: vi.fn(),
  }),
}));

import { ReviewTodayPanel } from "./ReviewTodayPanel";

const SESSION_UUID = "0198ad01-b200-7000-8000-000000000400";
const EMPTY_SIDE = { dueNow: 0, dueToday: 0, nextDueAt: null };

function renderPanel(locale: AppLocale = "ru-RU"): string {
  return renderToStaticMarkup(
    <LocaleProvider initialLocale={locale}>
      <MemoryRouter>
        <ReviewTodayPanel />
      </MemoryRouter>
    </LocaleProvider>,
  );
}

describe("ReviewTodayPanel", () => {
  beforeEach(() => {
    hookState.summary = { status: "loading" };
    hookState.startState = { status: "idle" };
  });

  it("shows due words per direction and the unfinished review", () => {
    hookState.summary = {
      status: "success",
      data: {
        timezone: "Europe/Moscow",
        sides: {
          front: { dueNow: 3, dueToday: 12, nextDueAt: "2026-11-06T18:30:00Z" },
          back: { dueNow: 0, dueToday: 0, nextDueAt: "2030-01-01T09:00:00Z" },
        },
        activeSession: {
          uuid: SESSION_UUID,
          promptSide: "front",
          answeredCount: 3,
          totalCount: 10,
        },
      },
    };

    const markup = renderPanel();

    expect(markup).toContain("Повторить сегодня");
    expect(markup).toContain('aria-label="Перевод → слово"');
    expect(markup).toContain('aria-label="Слово → перевод"');
    expect(markup).toContain("<strong>12</strong>");
    expect(markup).toContain("слов к повторению");
    expect(markup).not.toContain("Сейчас");
    expect(markup).toContain('aria-label="Повторить 12 слов: Перевод → слово"');
    expect(markup).toContain('title="Незаконченное повторение будет закрыто"');
    expect(markup.match(/<button/g)).toHaveLength(1);
    expect(markup).toContain("На сегодня всё");
    expect(markup).toContain('dateTime="2030-01-01T09:00:00Z"');
    expect(markup).toContain(`href="/practice?session=${SESSION_UUID}"`);
    expect(markup).toContain('aria-label="Продолжить повторение: отвечено 3 из 10"');
    expect(markup).toContain("width:30%");
  });

  it("explains an empty review list to a new learner", () => {
    hookState.summary = {
      status: "success",
      data: {
        timezone: "UTC",
        sides: { front: EMPTY_SIDE, back: EMPTY_SIDE },
        activeSession: null,
      },
    };

    const markup = renderPanel("en-US");

    expect(markup).toContain("Review today");
    expect(markup).toContain("Nothing to review yet");
    expect(markup).not.toContain("<button");
    expect(markup).not.toContain("/practice?session=");
  });

  it("shows when nothing is scheduled for a direction", () => {
    hookState.summary = {
      status: "success",
      data: {
        timezone: "UTC",
        sides: {
          front: { dueNow: 0, dueToday: 0, nextDueAt: "2030-01-01T09:00:00Z" },
          back: EMPTY_SIDE,
        },
        activeSession: null,
      },
    };

    const markup = renderPanel();

    expect(markup).toContain("Новых повторений пока нет");
    expect(markup.match(/На сегодня всё/g)).toHaveLength(2);
  });

  it("disables starting while a review is being prepared", () => {
    hookState.summary = {
      status: "success",
      data: {
        timezone: "UTC",
        sides: {
          front: { dueNow: 1, dueToday: 1, nextDueAt: null },
          back: { dueNow: 2, dueToday: 2, nextDueAt: null },
        },
        activeSession: null,
      },
    };
    hookState.startState = { status: "starting", side: "back" };

    const markup = renderPanel();

    expect(markup.match(/<button[^>]*disabled=""/g)).toHaveLength(2);
    expect(markup).toContain("Готовим…");
  });

  it.each([
    [
      new ApiError({ status: 409, code: "NO_CARDS_TO_REVIEW", message: "No cards" }),
      "Слова на сегодня уже повторены — список обновлён.",
    ],
    [
      new ApiError({ status: 0, code: "NETWORK_ERROR", message: "Failed to fetch" }),
      "Не удалось связаться с сервером. Проверьте подключение и попробуйте ещё раз.",
    ],
    [
      new ApiError({ status: 0, code: "INVALID_REVIEW_RESPONSE", message: "Bad" }),
      "Не удалось начать повторение. Попробуйте ещё раз.",
    ],
  ])("shows a readable start error", (error, message) => {
    hookState.summary = {
      status: "success",
      data: {
        timezone: "UTC",
        sides: { front: { dueNow: 1, dueToday: 1, nextDueAt: null }, back: EMPTY_SIDE },
        activeSession: null,
      },
    };
    hookState.startState = { status: "error", side: "front", error };

    expect(renderPanel()).toContain(`role="alert">${message}</p>`);
  });

  it("offers a retry when the summary did not load", () => {
    hookState.summary = { status: "error", error: new Error("boom") };

    const markup = renderPanel();

    expect(markup).toContain("Не удалось загрузить слова для повторения.");
    expect(markup).toContain("Попробовать снова");
  });

  it("renders an accessible loading placeholder", () => {
    expect(renderPanel()).toContain('aria-label="Загрузка слов для повторения"');
  });
});
