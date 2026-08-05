import type { UserSettings } from "../../features/settings/model/settings-types";
import type { AuthState, User } from "./auth-types";

export type AuthAction =
  | { type: "loading" }
  | { type: "authorized"; user: User }
  | { type: "settings-updated"; settings: UserSettings }
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
    case "settings-updated":
      return _state.status === "authorized" && _state.user !== null
        ? {
            ..._state,
            user: { ..._state.user, settings: action.settings },
          }
        : _state;
    case "unauthorized":
      return { status: "unauthorized", user: null, error: null };
    case "error":
      return { status: "error", user: null, error: action.error };
  }
}
