import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api";
import type { UseUserProfileResult } from "../../features/users/model/useUserProfile";
import { LocaleProvider } from "../../i18n";

const { authState, useUserProfileMock } = vi.hoisted(() => ({
  authState: { userUuid: "f9b7ced5-fbea-4741-82fd-33ea144dab7c" },
  useUserProfileMock: vi.fn(),
}));

vi.mock("../../auth/hooks/useAuth", () => ({
  useAuth: () => ({ user: { uuid: authState.userUuid } }),
}));

vi.mock("../../features/users/model/useUserProfile", () => ({
  useUserProfile: useUserProfileMock,
}));

import { UserProfilePage } from "./UserProfilePage";

const USER_UUID = "d2f61c35-11d0-489e-837d-3845418ba39e";
const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";

function createProfileResult(overrides: Partial<UseUserProfileResult> = {}): UseUserProfileResult {
  return {
    status: "success",
    profile: {
      uuid: USER_UUID,
      username: "deck-owner",
      createdAt: "2024-03-12T14:35:00Z",
      deckCount: 7,
      totalSavesCount: 42,
    },
    decks: [
      {
        uuid: DECK_UUID,
        ownerUuid: USER_UUID,
        ownerUsername: "deck-owner",
        title: "Daily Words",
        description: "Core vocabulary",
        totalWordsCount: 48,
        savesCount: 12,
        isSaved: false,
        isPublic: true,
        updatedAt: "2026-07-17T10:30:00Z",
      },
    ],
    nextCursor: "next-page",
    hasMore: true,
    error: null,
    isLoadingMore: false,
    loadMoreError: null,
    retry: vi.fn(),
    loadMore: vi.fn(),
    setSaved: vi.fn(),
    savingDeckUuids: [],
    saveErrors: {},
    ...overrides,
  };
}

function renderProfile(pathname = "/users/deck-owner"): string {
  return renderToStaticMarkup(
    <LocaleProvider initialLocale="ru-RU">
      <MemoryRouter initialEntries={[pathname]}>
        <Routes>
          <Route element={<UserProfilePage />} path="/users/:username" />
        </Routes>
      </MemoryRouter>
    </LocaleProvider>,
  );
}

describe("UserProfilePage", () => {
  beforeEach(() => {
    authState.userUuid = "f9b7ced5-fbea-4741-82fd-33ea144dab7c";
    useUserProfileMock.mockReset();
    useUserProfileMock.mockReturnValue(createProfileResult());
  });

  it("renders profile metadata and catalog-style deck actions", () => {
    const markup = renderProfile();

    expect(useUserProfileMock).toHaveBeenCalledWith("deck-owner");
    expect(markup).toContain("<h1>@deck-owner</h1>");
    expect(markup).toContain("Профиль пользователя");
    expect(markup).toContain("Колоды пользователя");
    expect(markup).not.toContain('data-own-profile="true"');
    expect(markup).not.toContain("Это вы");
    expect(markup).toContain(">@deck-owner</span>");
    expect(markup).not.toContain('<circle cx="12" cy="8.2" r="3.2"');
    expect(markup).toContain("Колоды");
    expect(markup).toContain(">7<");
    expect(markup).toContain("Сохранения колод");
    expect(markup).toContain(">42<");
    expect(markup).toContain('<time dateTime="2024-03-12T14:35:00Z">');
    expect(markup).toContain(">12 марта 2024 г.</time>");
    expect(markup).toContain("Daily Words");
    expect(markup).toContain("48 слов");
    expect(markup).toContain("12 сохранений");
    expect(markup).toContain(`href="/decks/${DECK_UUID}"`);
    expect(markup).toContain(`href="/practice?deck=${DECK_UUID}"`);
    expect(markup).toContain('aria-pressed="false"');
    expect(markup).toContain("Сохранить");
    expect(markup).toContain("Предпросмотр");
    expect(markup).toContain("Показать ещё");

    useUserProfileMock.mockReturnValue(createProfileResult({ savingDeckUuids: [DECK_UUID] }));
    const savingMarkup = renderProfile();
    expect(savingMarkup).toMatch(/<button[^>]*aria-busy="true"[^>]*disabled=""/);
    expect(savingMarkup).toContain("Сохраняем…");

    useUserProfileMock.mockReturnValue(
      createProfileResult({
        saveErrors: { [DECK_UUID]: new Error("Internal backend detail") },
      }),
    );
    const failedMarkup = renderProfile();
    expect(failedMarkup).toContain('role="alert"');
    expect(failedMarkup).toContain("Не удалось изменить сохранение колоды.");
    expect(failedMarkup).not.toContain("Internal backend detail");
    expect(failedMarkup).toContain('aria-pressed="false"');
  });

  it("marks the current user's profile by comparing the two UUIDs", () => {
    authState.userUuid = USER_UUID.toUpperCase();

    const markup = renderProfile();

    expect(markup).toContain('data-own-profile="true"');
    expect(markup).toContain("Ваш профиль");
    expect(markup).toContain("Это вы");
    expect(markup).toContain("Ваши колоды");
    expect(markup).not.toContain("Профиль пользователя");
    expect(markup).not.toContain("Колоды пользователя");
    expect(markup).toContain("В библиотеке");
    expect(markup).not.toContain('aria-pressed="false"');
  });

  it("renders a safe not-found message", () => {
    useUserProfileMock.mockReturnValue(
      createProfileResult({
        status: "error",
        profile: null,
        decks: [],
        hasMore: false,
        nextCursor: null,
        error: new ApiError({ status: 404, message: "Internal backend detail" }),
      }),
    );

    const markup = renderProfile("/users/missing-user");

    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Пользователь с таким никнеймом не найден.");
    expect(markup).not.toContain("Internal backend detail");
  });
});
