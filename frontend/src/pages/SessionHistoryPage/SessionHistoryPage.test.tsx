import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PracticeSessionHistoryItem } from "../../features/practice/model/practice-types";
import type { UsePracticeSessionHistoryResult } from "../../features/practice/model/usePracticeSessionHistory";

const usePracticeSessionHistoryMock = vi.hoisted(() => vi.fn());

vi.mock("../../features/practice/model/usePracticeSessionHistory", () => ({
  usePracticeSessionHistory: usePracticeSessionHistoryMock,
}));

import { SessionHistoryPage } from "./SessionHistoryPage";

const SESSION_UUID = "413b1910-5d07-4c67-93a0-6b8946c59b15";

function createItem(
  overrides: Partial<PracticeSessionHistoryItem> = {},
): PracticeSessionHistoryItem {
  return {
    itemUuid: "019c05e5-bc86-70e6-8f5c-d31bfa1aac10",
    sequenceNumber: 1,
    promptText: "bonjour",
    answerText: "привет",
    promptLanguage: "fr",
    answerLanguage: "ru",
    userTypedText: "привет",
    isAnswered: true,
    isCorrect: true,
    ...overrides,
  };
}

function renderPage(path: string): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<SessionHistoryPage />} path="/practice/sessions/:session_uuid/history" />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SessionHistoryPage", () => {
  beforeEach(() => {
    usePracticeSessionHistoryMock.mockReset();
    usePracticeSessionHistoryMock.mockReturnValue({
      state: { status: "loading", sessionUuid: SESSION_UUID },
      retry: vi.fn(),
    } satisfies UsePracticeSessionHistoryResult);
  });

  it("renders compact card pairs and visual outcomes", () => {
    usePracticeSessionHistoryMock.mockReturnValue({
      state: {
        status: "ready",
        sessionUuid: SESSION_UUID,
        items: [
          createItem(),
          createItem({
            itemUuid: "019c05e5-bc86-70e6-8f5c-d31bfa1aac11",
            sequenceNumber: 2,
            promptText: "merci",
            answerText: "спасибо",
            userTypedText: "спосибо",
            isCorrect: false,
          }),
          createItem({
            itemUuid: "019c05e5-bc86-70e6-8f5c-d31bfa1aac12",
            sequenceNumber: 3,
            promptText: "au revoir",
            answerText: "до свидания",
            userTypedText: null,
            isAnswered: false,
            isCorrect: null,
          }),
          createItem({
            itemUuid: "019c05e5-bc86-70e6-8f5c-d31bfa1aac13",
            sequenceNumber: 4,
            promptText: "salut",
            answerText: "пока",
            userTypedText: null,
            isCorrect: false,
          }),
        ],
      },
      retry: vi.fn(),
    } satisfies UsePracticeSessionHistoryResult);

    const markup = renderPage(`/practice/sessions/${SESSION_UUID}/history`);

    expect(markup).toContain("История сессии");
    expect(markup).toContain("bonjour");
    expect(markup).toContain("привет");
    expect(markup).toContain('aria-label="Верно"');
    expect(markup).toContain('aria-label="Ошибка"');
    expect(markup).toContain('aria-label="Пропущено"');
    expect(markup).toContain('aria-label="Не отвечено"');
    expect(markup).toContain("Ваш ответ");
    expect(markup).toContain("Правильно");
    expect(markup).toContain("спосибо");
    expect(markup).toContain("спасибо");
    expect(markup).toContain("пока");
    expect(markup).not.toContain("до свидания");
    expect(usePracticeSessionHistoryMock).toHaveBeenCalledWith(SESSION_UUID);
  });

  it("rejects a malformed route parameter without loading a session", () => {
    usePracticeSessionHistoryMock.mockReturnValue({
      state: { status: "idle" },
      retry: vi.fn(),
    } satisfies UsePracticeSessionHistoryResult);

    const markup = renderPage("/practice/sessions/not-a-uuid/history");

    expect(markup).toContain("Некорректная ссылка");
    expect(usePracticeSessionHistoryMock).toHaveBeenCalledWith(null);
  });
});
