import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const { retryMock } = vi.hoisted(() => ({ retryMock: vi.fn() }));

vi.mock("../../features/home/model/useHomeDashboard", () => ({
  useHomeDashboard: () => ({
    status: "success",
    data: {
      decks: [
        {
          title: "Daily Words",
          description: "Core vocabulary",
          totalWordsCount: 48,
          accuracy: 72,
          updatedAt: "2026-07-17T10:30:00Z",
        },
        {
          title: "Travel Essentials",
          description: null,
          totalWordsCount: 36,
          accuracy: 64,
          updatedAt: null,
        },
      ],
      progress: {
        wordsExplored: 84,
        weeklyAccuracy: 76,
        currentStreakDays: 7,
        totalStudyTimeSeconds: 4_200,
      },
      weeklyActivity: [
        { date: "2026-07-12", percent: 40 },
        { date: "2026-07-13", percent: 70 },
        { date: "2026-07-14", percent: 55 },
        { date: "2026-07-15", percent: 80 },
        { date: "2026-07-16", percent: 30 },
        { date: "2026-07-17", percent: 60 },
        { date: "2026-07-18", percent: 90 },
      ],
    },
    error: null,
    retry: retryMock,
  }),
}));

import { HomePage } from "./HomePage";

describe("HomePage", () => {
  it("renders BFF dashboard content without duplicating the app navigation", () => {
    const markup = renderToStaticMarkup(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    const accuracyTooltipIds = [...markup.matchAll(/aria-describedby="([^"]+)"/g)].map(
      ([, id]) => id,
    );

    expect(markup).not.toContain('aria-label="Основная навигация"');
    expect(markup).toContain("Daily Words");
    expect(markup).toContain("Travel Essentials");
    expect(markup).toContain('href="/library"');
    expect(markup).not.toContain('viewBox="0 0 160 140"');
    expect(markup.match(/role="meter"/g)).toHaveLength(2);
    expect(markup).toContain('aria-valuenow="72"');
    expect(markup).toContain('aria-valuetext="72%"');
    expect(markup).toMatch(/<span[^>]*role="meter"[^>]*tabindex="0">72<\/span>/);
    expect(markup).toMatch(/<span[^>]*role="meter"[^>]*tabindex="0">64<\/span>/);
    expect(markup.match(/role="tooltip"/g)).toHaveLength(2);
    expect(new Set(accuracyTooltipIds).size).toBe(2);
    accuracyTooltipIds.forEach((id) => expect(markup).toContain(`id="${id}"`));
    expect(markup).toContain("Точность колоды");
    expect(markup).toContain("Правильных ответов — 72%");
    expect(markup).not.toContain('title="Точность:');
    expect(markup).not.toContain('role="progressbar"');
    expect(markup).toContain('dateTime="2026-07-17T10:30:00Z"');
    expect(markup).toContain("Обновлено");
    expect(markup.match(/<time /g)).toHaveLength(1);
    expect(markup).toContain("Вс, 2026-07-12: 40%");
    expect(markup).toContain("Сб, 2026-07-18: 90%");
  });
});
