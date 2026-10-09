export const AUTH_ENDPOINTS = {
  challenge: "/auth/challenge",
  login: "/auth/login",
  logout: "/auth/logout",
  refresh: "/auth/refresh",
} as const;

export const USER_ENDPOINTS = {
  create: "/users/create",
  me: "/users/me",
  settings: "/users/me/settings",
} as const;
