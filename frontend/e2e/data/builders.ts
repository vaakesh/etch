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
    timezone: string;
  };
}

export function buildCurrentUser(): CurrentUserResponse {
  return {
    uuid: "01900000-0000-7000-8000-000000000001",
    username: "e2e_student",
    email: "e2e-student@example.test",
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
    settings: {
      locale: "ru-RU",
      theme: "light",
      show_previews_for_long: true,
      timezone: "Europe/Moscow",
    },
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

// ReviewSummaryResponse of GET /bff/reviews/summary (backend/app/training_sessions/schemas.py).
export interface ReviewSideSummaryResponse {
  due_now: number;
  due_today: number;
  next_due_at: string | null;
}

export interface ReviewSummaryResponse {
  timezone: string;
  sides: { front: ReviewSideSummaryResponse; back: ReviewSideSummaryResponse };
  active_session: {
    training_session_uuid: string;
    prompt_side: "front" | "back";
    answered_count: number;
    total_count: number;
  } | null;
}

/** A user who has not practised yet: nothing to review and nothing scheduled. */
export function buildEmptyReviewSummary(): ReviewSummaryResponse {
  const side = { due_now: 0, due_today: 0, next_due_at: null };
  return {
    timezone: "UTC",
    sides: { front: { ...side }, back: { ...side } },
    active_session: null,
  };
}

/** Two words due today in the "translation → word" direction, nothing in the other one. */
export function buildReviewSummaryWithDueWords(): ReviewSummaryResponse {
  return {
    timezone: "Europe/Moscow",
    sides: {
      front: { due_now: 2, due_today: 2, next_due_at: null },
      back: { due_now: 0, due_today: 0, next_due_at: null },
    },
    active_session: null,
  };
}

// PracticeSessionResponse of POST /bff/reviews/start and GET /bff/practice/{uuid}/resume.
export function buildReviewSession(sessionUuid: string) {
  return {
    training_session_uuid: sessionUuid,
    kind: "review",
    deck_uuid: null,
    prompt_side: "front",
    answer_side: "back",
    total_count: 2,
    answered_count: 0,
    correct_count: 0,
    wrong_count: 0,
    started_at: "2026-11-06T09:00:00Z",
    cards: [
      { sequence_number: 1, prompt_text: "кот", prompt_language: "ru", answer_language: "en" },
      { sequence_number: 2, prompt_text: "пёс", prompt_language: "ru", answer_language: "en" },
    ],
  };
}

// SubmitAnswerResponse of PUT /training-sessions/{uuid}/items/{n}/submit: the first of two
// cards answered correctly.
export function buildFirstCorrectAnswer(answerText: string) {
  return {
    is_correct: true,
    answer_text: answerText,
    answered_count: 1,
    correct_count: 1,
    total_count: 2,
    is_finished: false,
    time_to_complete: null,
    next_review_at: "2026-11-06T09:10:00Z",
  };
}

// RateAnswerResponse of PUT /training-sessions/{uuid}/items/{n}/rating.
export function buildRateAnswerResponse(rating: 1 | 2 | 3 | 4) {
  return { rating, next_review_at: "2026-11-09T09:00:00Z" };
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
