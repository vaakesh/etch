import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api";
import type { PracticeSession } from "../../features/practice/model/practice-types";
import type {
  ReadyPracticeState,
  UsePracticeSessionResult,
} from "../../features/practice/model/usePracticeSession";

const usePracticeSessionMock = vi.hoisted(() => vi.fn());

vi.mock("../../features/practice/model/usePracticeSession", () => ({
  usePracticeSession: usePracticeSessionMock,
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

function renderPractice(pathname: string, state?: unknown): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[state === undefined ? pathname : { pathname, state }]}>
      <PracticePage />
    </MemoryRouter>,
  );
}

describe("PracticePage", () => {
  beforeEach(() => {
    usePracticeSessionMock.mockReset();
    usePracticeSessionMock.mockReturnValue(createPracticeResult());
  });

  it("directs a bare practice route to deck selection", () => {
    const markup = renderPractice("/practice");

    expect(markup).toContain("Сначала выберите колоду");
    expect(markup).toContain('href="/library"');
    expect(markup).toContain('data-practice-mode="setup"');
    expect(usePracticeSessionMock).toHaveBeenCalledWith(null, null);
  });

  it("renders the backend-supported setup choices without unavailable card limits", () => {
    const markup = renderPractice(`/practice?deck=${DECK_UUID}`);

    expect(markup).toContain("Как будем тренироваться?");
    expect(markup).toContain('name="prompt_side"');
    expect(markup).toContain('value="front"');
    expect(markup).toContain('value="back"');
    expect(markup).toContain("Вся колода");
    expect(markup).not.toContain(">50<");
    expect(markup).not.toContain(">100<");
    expect(markup).toContain("Начать");
    expect(usePracticeSessionMock).toHaveBeenCalledWith(null, DECK_UUID);
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
    expect(markup.match(/<fieldset[^>]*disabled=""/g)).toHaveLength(1);
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
    expect(markup).not.toContain("Сначала выберите колоду");
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
