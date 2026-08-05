export const AUTH_ENDPOINTS = {
  login: "/auth/login",
  logout: "/auth/logout",
  refresh: "/auth/refresh",
} as const;

export const USER_ENDPOINTS = {
  me: "/users/me",
  settings: "/users/me/settings",
} as const;
