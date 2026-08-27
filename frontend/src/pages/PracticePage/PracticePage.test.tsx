import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api";
import type {
  PracticeHistorySession,
  PracticeSession,
} from "../../features/practice/model/practice-types";
import type { UsePracticeHistoryResult } from "../../features/practice/model/usePracticeHistory";
import type {
  ReadyPracticeState,
  UsePracticeSessionResult,
} from "../../features/practice/model/usePracticeSession";
import { LocaleProvider, type AppLocale } from "../../i18n";

const usePracticeSessionMock = vi.hoisted(() => vi.fn());
const usePracticeDeckAvailabilityMock = vi.hoisted(() => vi.fn());
const usePracticeHistoryMock = vi.hoisted(() => vi.fn());
const resetPracticeHistoryCacheMock = vi.hoisted(() => vi.fn());

vi.mock("../../features/practice/model/usePracticeSession", () => ({
  usePracticeSession: usePracticeSessionMock,
}));

vi.mock("../../features/practice/model/usePracticeDeckAvailability", () => ({
  usePracticeDeckAvailability: usePracticeDeckAvailabilityMock,
}));

vi.mock("../../features/practice/model/usePracticeHistory", () => ({
  resetPracticeHistoryCache: resetPracticeHistoryCacheMock,
  usePracticeHistory: usePracticeHistoryMock,
}));

import { ActivePracticeSessionView, PracticeCompletionView, PracticePage } from "./PracticePage";

const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const SESSION_UUID = "413b1910-5d07-4c67-93a0-6b8946c59b15";

function createSession(overrides: Partial<PracticeSession> = {}): PracticeSession {
  return {
    uuid: SESSION_UUID,
    deckUuid: DECK_UUID,
    promptSide: "front",
    answerSide: "back",
    totalCount: 12,
    answeredCount: 0,
    correctCount: 0,
    wrongCount: 0,
    startedAt: "2026-08-01T12:00:00Z",
    cards: Array.from({ length: 12 }, (_, index) => ({
      sequenceNumber: index + 1,
      promptText: index === 0 ? "indelible" : `word ${index + 1}`,
      promptLanguage: "en",
      answerLanguage: "ru",
    })),
    ...overrides,
  };
}

function createReadyState(overrides: Partial<ReadyPracticeState> = {}): ReadyPracticeState {
  return {
    status: "ready",
    session: createSession(),
    feedbackBySequence: {},
    isFinished: false,
    timeToCompleteSeconds: null,
    submittingSequenceNumber: null,
    submitError: null,
    ...overrides,
  };
}

function createPracticeResult(
  state: UsePracticeSessionResult["state"] = { status: "idle" },
): UsePracticeSessionResult {
  return {
    state,
    retryResume: vi.fn(),
    start: vi.fn(async () => null),
    submit: vi.fn(async () => null),
  };
}

function createHistorySession(
  overrides: Partial<PracticeHistorySession> = {},
): PracticeHistorySession {
  return {
    uuid: SESSION_UUID,
    deckUuid: DECK_UUID,
    status: "completed",
    requestedCount: 12,
    actualCount: 12,
    correctCount: 9,
    wrongCount: 3,
    promptSide: "front",
    answerSide: "back",
    startedAt: "2026-08-01T12:00:00Z",
    finishedAt: "2026-08-01T12:04:00Z",
    ...overrides,
  };
}

function createHistoryResult(
  state: UsePracticeHistoryResult["state"] = { status: "ready", sessions: [] },
): UsePracticeHistoryResult {
  return { state, retry: vi.fn() };
}

function renderPractice(pathname: string, state?: unknown, locale: AppLocale = "ru-RU"): string {
  return renderToStaticMarkup(
    <LocaleProvider initialLocale={locale}>
      <MemoryRouter initialEntries={[state === undefined ? pathname : { pathname, state }]}>
        <PracticePage />
      </MemoryRouter>
    </LocaleProvider>,
  );
}

describe("PracticePage", () => {
  beforeEach(() => {
    usePracticeSessionMock.mockReset();
    usePracticeSessionMock.mockReturnValue(createPracticeResult());
    usePracticeDeckAvailabilityMock.mockReset();
    usePracticeDeckAvailabilityMock.mockImplementation((deckUuid: string | null) => ({
      state:
        deckUuid === null ? { status: "idle" } : { status: "ready", deckUuid, wordsCount: 120 },
      retry: vi.fn(),
    }));
    usePracticeHistoryMock.mockReset();
    usePracticeHistoryMock.mockReturnValue(createHistoryResult());
    resetPracticeHistoryCacheMock.mockReset();
  });

  it("shows training history and filters on the bare practice route", () => {
    const markup = renderPractice("/practice");

    expect(markup).toContain("Тренировочные сессии");
    expect(markup).toContain("Завершённые");
    expect(markup).toContain("Незавершённые");
    expect(markup).toContain("Брошенные");
    expect(markup).toContain("Здесь появятся ваши тренировки");
    expect(markup).toContain('data-practice-mode="setup"');
    expect(markup).not.toContain('aria-label="На главную"');
    expect(markup).not.toContain('aria-label="Выйти из практики в библиотеку"');
    expect(usePracticeSessionMock).toHaveBeenCalledWith(null, null);
    expect(usePracticeHistoryMock).toHaveBeenCalledWith("all");
  });

  it("renders practice history and filters in English", () => {
    const markup = renderPractice("/practice", undefined, "en-US");

    expect(markup).toContain("Practice sessions");
    expect(markup).toContain("Completed");
    expect(markup).toContain("In progress");
    expect(markup).toContain("Abandoned");
    expect(markup).toContain("Your practice sessions will appear here");
  });

  it("renders active preset and custom session limits", () => {
    const markup = renderPractice(`/practice?deck=${DECK_UUID}`);

    expect(markup).toContain("Настройка сессии");
    expect(markup).toContain('name="prompt_side"');
    expect(markup).toContain('value="front"');
    expect(markup).toContain('value="back"');
    expect(markup).toContain('aria-label="Перевод в слово"');
    expect(markup).toContain('aria-label="Слово в перевод"');
    expect(markup).not.toContain("→");
    expect(markup).toContain("Вся колода");
    expect(markup).toContain("50 карточек");
    expect(markup).toContain("100 карточек");
    expect(markup).toContain("Своё значение");
    expect(markup.match(/<input[^>]*value="50"[^>]*>/)?.[0]).not.toContain("disabled");
    expect(markup.match(/<input[^>]*value="100"[^>]*>/)?.[0]).not.toContain("disabled");
    expect(markup.match(/<input[^>]*value="custom"[^>]*>/)?.[0]).not.toContain("disabled");
    expect(markup.match(/<input[^>]*aria-label="Количество карточек"[^>]*>/)?.[0]).not.toContain(
      "disabled",
    );
    expect(markup).toContain("Начать");
    expect(usePracticeSessionMock).toHaveBeenCalledWith(null, DECK_UUID);
    expect(usePracticeDeckAvailabilityMock).toHaveBeenCalledWith(DECK_UUID);
  });

  it.each([403, 404])("renders a private deck-safe not-found state for status %s", (status) => {
    usePracticeDeckAvailabilityMock.mockReturnValue({
      state: {
        status: "error",
        deckUuid: DECK_UUID,
        error: new ApiError({ status, message: "Internal backend detail" }),
      },
      retry: vi.fn(),
    });

    const markup = renderPractice(`/practice?deck=${DECK_UUID}`);

    expect(markup).toContain("Колода не найдена");
    expect(markup).toContain("Возможно, она была удалена или ссылка больше недоступна");
    expect(markup).not.toContain("Internal backend detail");
    expect(markup).not.toContain("нет доступа");
    expect(markup).not.toContain("Настройка сессии");
  });

  it("checks deck availability before showing practice setup", () => {
    usePracticeDeckAvailabilityMock.mockReturnValue({
      state: { status: "loading", deckUuid: DECK_UUID },
      retry: vi.fn(),
    });

    const markup = renderPractice(`/practice?deck=${DECK_UUID}`);

    expect(markup).toContain("Проверяем колоду");
    expect(markup).not.toContain("Настройка сессии");
  });

  it("renders previous sessions with their status, direction, counters, and repeat action", () => {
    usePracticeHistoryMock.mockReturnValue(
      createHistoryResult({
        status: "ready",
        sessions: [
          createHistorySession(),
          createHistorySession({
            uuid: "019c05e5-bc86-70e6-8f5c-d31bfa1aac11",
            status: "in_progress",
            actualCount: 4,
            correctCount: 3,
            wrongCount: 1,
            promptSide: "back",
            answerSide: "front",
            finishedAt: null,
          }),
          createHistorySession({
            uuid: "019c05e5-bc86-70e6-8f5c-d31bfa1aac12",
            status: "abandoned",
            actualCount: 2,
            correctCount: 1,
            wrongCount: 1,
            finishedAt: null,
          }),
        ],
      }),
    );

    const markup = renderPractice("/practice");

    expect(markup).toContain("Завершена");
    expect(markup).toContain("Не завершена");
    expect(markup).toContain("Брошена");
    expect(markup).toContain('aria-label="Слово в перевод"');
    expect(markup).toContain('aria-label="Перевод в слово"');
    expect(markup).not.toContain("→");
    expect(markup.match(/Повторить/g)).toHaveLength(2);
    expect(markup.match(/Продолжить/g)).toHaveLength(1);
    expect(markup.match(/aria-label="Точность сессии"/g)).toHaveLength(3);
    expect(markup.match(/aria-describedby=/g)).toHaveLength(3);
    expect(markup.match(/role="meter"/g)).toHaveLength(3);
    expect(markup.match(/role="tooltip"/g)).toHaveLength(3);
    expect(markup.match(/tabindex="0"/g)).toHaveLength(3);
    expect(markup).toContain("Правильных ответов — 75%");
    expect(markup.match(/aria-label="Открыть историю сессии"/g)).toHaveLength(2);
    expect(markup).toContain(`/practice/sessions/${SESSION_UUID}/history`);
    expect(markup).toContain("/practice/sessions/019c05e5-bc86-70e6-8f5c-d31bfa1aac12/history");
    expect(markup).not.toContain("/practice/sessions/019c05e5-bc86-70e6-8f5c-d31bfa1aac11/history");
  });

  it("loads resume mode from the session query and renders the active card", () => {
    usePracticeSessionMock.mockReturnValue(createPracticeResult(createReadyState()));

    const markup = renderPractice(`/practice?session=${SESSION_UUID}`);

    expect(usePracticeSessionMock).toHaveBeenCalledWith(SESSION_UUID, null);
    expect(markup).toContain('data-practice-mode="session"');
    expect(markup).toContain("indelible");
    expect(markup).toContain("EN");
    expect(markup).toContain("RU");
    expect(markup).toContain('role="progressbar"');
    expect(markup).toContain('aria-label="Карточки сессии"');
    expect(markup).toContain('placeholder="Ваш ответ"');
    expect(markup).toContain("карточек пропущено");
  });

  it("reduces the prompt size before a long word wraps by a few characters", () => {
    usePracticeSessionMock.mockReturnValue(
      createPracticeResult(
        createReadyState({
          session: createSession({
            cards: [
              {
                sequenceNumber: 1,
                promptText: "приостанавливать",
                promptLanguage: "ru",
                answerLanguage: "en",
              },
            ],
            totalCount: 1,
          }),
        }),
      ),
    );

    const markup = renderPractice(`/practice?session=${SESSION_UUID}`);

    expect(markup).toMatch(/<h1[^>]*data-text-size="medium"[^>]*>приостанавливать<\/h1>/);
  });

  it("does not offer a futile retry when resume reports a finished session", () => {
    const retryResume = vi.fn();
    usePracticeSessionMock.mockReturnValue({
      ...createPracticeResult({
        status: "error",
        operation: "resume",
        error: new ApiError({ status: 409, message: "Already finished" }),
      }),
      retryResume,
    });

    const markup = renderPractice(`/practice?session=${SESSION_UUID}`);

    expect(markup).toContain("Эта тренировочная сессия уже завершена");
    expect(markup).not.toContain("Попробовать снова");
    expect(markup).toContain("Выбрать новую тренировку");
    expect(markup).toContain('role="alert"');
  });

  it.each([403, 404])("does not reveal a hidden session for resume status %s", (status) => {
    usePracticeSessionMock.mockReturnValue(
      createPracticeResult({
        status: "error",
        operation: "resume",
        error: new ApiError({ status, message: "Internal backend detail" }),
      }),
    );

    const markup = renderPractice(`/practice?session=${SESSION_UUID}`);

    expect(markup).toContain("Тренировка не найдена");
    expect(markup).toContain("Тренировочная сессия не найдена или больше недоступна");
    expect(markup).not.toContain("Internal backend detail");
    expect(markup).not.toContain("нет доступа");
    expect(markup).not.toContain("Попробовать снова");
  });

  it.each([403, 404])(
    "leaves the card UI when a submit reports missing session status %s",
    (status) => {
      usePracticeSessionMock.mockReturnValue(
        createPracticeResult(
          createReadyState({
            submitError: {
              sequenceNumber: 1,
              error: new ApiError({ status, message: "Internal backend detail" }),
            },
          }),
        ),
      );

      const markup = renderPractice(`/practice?session=${SESSION_UUID}`);

      expect(markup).toContain("Тренировка не найдена");
      expect(markup).not.toContain("Internal backend detail");
      expect(markup).not.toContain('placeholder="Ваш ответ"');
    },
  );

  it("rejects conflicting deck and session query values without a backend request", () => {
    const markup = renderPractice(`/practice?deck=${DECK_UUID}&session=${SESSION_UUID}`);

    expect(markup).toContain("Некорректная ссылка");
    expect(markup).toContain("Выберите колоду заново");
    expect(usePracticeSessionMock).toHaveBeenCalledWith(null, null);
  });

  it("normalizes uppercase UUID query values before loading", () => {
    usePracticeSessionMock.mockReturnValue(createPracticeResult(createReadyState()));

    renderPractice(`/practice?session=${SESSION_UUID.toUpperCase()}`);

    expect(usePracticeSessionMock).toHaveBeenCalledWith(SESSION_UUID, null);
  });

  it("disables setup choices while the start request is pending", () => {
    usePracticeSessionMock.mockReturnValue(
      createPracticeResult({ status: "loading", operation: "start" }),
    );

    const markup = renderPractice(`/practice?deck=${DECK_UUID}`);

    expect(markup).toContain('aria-busy="true"');
    expect(markup.match(/<fieldset[^>]*disabled=""/g)).toHaveLength(2);
  });

  it("restores the completion summary from navigation history state", () => {
    const markup = renderPractice("/practice", {
      practiceCompletion: {
        sessionUuid: SESSION_UUID,
        deckUuid: DECK_UUID,
        totalCount: 12,
        correctCount: 9,
        wrongCount: 3,
        timeToCompleteSeconds: 154,
      },
    });

    expect(markup).toContain("Колода пройдена");
    expect(markup).toContain("75%");
    expect(markup).toContain("2 мин 34 сек");
    expect(markup).not.toContain("Тренировочные сессии");
  });

  it("restores a persisted result when reload confirms that the session is finished", () => {
    usePracticeSessionMock.mockReturnValue(
      createPracticeResult({
        status: "error",
        operation: "resume",
        error: new ApiError({ status: 409, message: "Already finished" }),
      }),
    );

    const markup = renderToStaticMarkup(
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/practice",
            search: `?session=${SESSION_UUID}`,
            state: {
              practiceCompletion: {
                sessionUuid: SESSION_UUID,
                deckUuid: DECK_UUID,
                totalCount: 12,
                correctCount: 9,
                wrongCount: 3,
                timeToCompleteSeconds: 154,
              },
            },
          },
        ]}
      >
        <PracticePage />
      </MemoryRouter>,
    );

    expect(markup).toContain("Колода пройдена");
    expect(markup).not.toContain("Не получилось продолжить");
  });
});

describe("active practice feedback", () => {
  it("keeps a wrong answer visible with the canonical backend answer", () => {
    const state = createReadyState({
      session: createSession({ answeredCount: 1, wrongCount: 1 }),
      feedbackBySequence: {
        1: {
          action: "answer",
          answerText: "неизгладимый",
          isCorrect: false,
          submittedAnswer: "вечный",
        },
      },
    });

    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <ActivePracticeSessionView
          onComplete={vi.fn()}
          onSubmit={vi.fn(async () => null)}
          state={state}
        />
      </MemoryRouter>,
    );

    expect(markup).toContain("Не совсем");
    expect(markup).toContain("Правильный ответ");
    expect(markup).toContain("неизгладимый");
    expect(markup).toContain("Дальше");
    expect(markup).not.toContain("Введите перевод");
  });

  it("renders the final summary with score, errors, duration, and restart link", () => {
    const session = createSession({
      answeredCount: 12,
      correctCount: 9,
      wrongCount: 3,
      cards: [],
    });

    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <PracticeCompletionView
          summary={{
            sessionUuid: session.uuid,
            deckUuid: session.deckUuid,
            totalCount: session.totalCount,
            correctCount: session.correctCount,
            wrongCount: session.wrongCount,
            timeToCompleteSeconds: 154,
          }}
        />
      </MemoryRouter>,
    );

    expect(markup).toContain("75%");
    expect(markup).toContain("Колода пройдена");
    expect(markup).toContain("2 мин 34 сек");
    expect(markup).toContain(`<dd>9</dd>`);
    expect(markup).toContain(`<dd>3</dd>`);
    expect(markup).toContain(`href="/practice?deck=${DECK_UUID}"`);
  });
});
