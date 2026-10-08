import type { UserSettings } from "../../features/settings/model/settings-types";

export type AuthStatus = "loading" | "authorized" | "unauthorized" | "error";

export interface User {
  uuid: string;
  username: string;
  email: string;
  settings: UserSettings;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface RegistrationCredentials extends LoginCredentials {
  email: string;
}

export interface AuthState {
  status: AuthStatus;
  user: User | null;
  error: Error | null;
  /** The session ended without the user asking for it (rejected by the server), not by logout. */
  sessionExpired: boolean;
}

export interface AuthContextValue extends AuthState {
  isAuthenticated: boolean;
  initialize: () => Promise<void>;
  login: (credentials: LoginCredentials, signal?: AbortSignal) => Promise<void>;
  logout: (signal?: AbortSignal) => Promise<void>;
  refresh: (signal?: AbortSignal) => Promise<void>;
  applyUserSettings: (settings: UserSettings) => void;
}
