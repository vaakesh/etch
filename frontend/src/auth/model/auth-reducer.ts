import type { AuthState, User } from "./auth-types";

export type AuthAction =
  | { type: "loading" }
  | { type: "authorized"; user: User }
  | { type: "unauthorized" }
  | { type: "error"; error: Error };

export const initialAuthState: AuthState = {
  status: "loading",
  user: null,
  error: null,
};

export function authReducer(_state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case "loading":
      return { status: "loading", user: null, error: null };
    case "authorized":
      return { status: "authorized", user: action.user, error: null };
    case "unauthorized":
      return { status: "unauthorized", user: null, error: null };
    case "error":
      return { status: "error", user: null, error: action.error };
  }
}
