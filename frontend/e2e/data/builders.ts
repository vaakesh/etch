// Wire contracts: backend/app/users/schemas.py and backend/app/bff/schemas.py.
export interface CurrentUserResponse {
  uuid: string;
  username: string;
  email: string;
  created_at: string;
  updated_at: string;
  settings: {
    locale: "ru-RU" | "en-US";
    theme: "light" | "dark" | "system";
    show_previews_for_long: boolean;
  };
}

export function buildCurrentUser(): CurrentUserResponse {
  return {
    uuid: "01900000-0000-7000-8000-000000000001",
    username: "e2e_student",
    email: "e2e-student@example.test",
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
    settings: { locale: "ru-RU", theme: "light", show_previews_for_long: true },
  };
}

// UserProfileResponse of GET /users/profile/{username} for a user without decks.
export function buildEmptyUserProfile(user: CurrentUserResponse) {
  return {
    uuid: user.uuid,
    username: user.username,
    created_at: user.created_at,
    deck_count: 0,
    total_saves_count: 0,
  };
}

// CursorPage[...] with no items: the last (and only) page of any cursor-paginated list.
export function buildEmptyCursorPage() {
  return { items: [], next_cursor: null, has_more: false };
}

export function buildEmptyHome() {
  return {
    decks: [],
    progress: {
      user_words_explored: 0,
      user_weekly_accuracy: 0,
      user_current_streak: 0,
      user_total_study_time: 0,
    },
    user_weekly_activity: [],
  };
}
