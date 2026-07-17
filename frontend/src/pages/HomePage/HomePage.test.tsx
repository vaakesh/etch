import { renderToStaticMarkup } from "react-dom/server";
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
      weeklyActivity: [40, 70, 55, 80, 30, 60, 90],
    },
    error: null,
    retry: retryMock,
  }),
}));

import { HomePage } from "./HomePage";

describe("HomePage", () => {
  it("renders an accessible expanded sidebar control and BFF dashboard content", () => {
    const markup = renderToStaticMarkup(<HomePage />);

    expect(markup).toContain("Etch");
    expect(markup).toContain('id="home-sidebar"');
    expect(markup).toContain('aria-controls="home-sidebar"');
    expect(markup).toContain('aria-expanded="true"');
    expect(markup).toContain('aria-label="Свернуть боковое меню"');
    expect(markup).toContain("Daily Words");
    expect(markup).toContain("Travel Essentials");
  });
});
