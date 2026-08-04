function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export const LOGIN_PATH = "/login";
export const HOME_PATH = "/";
export const SESSION_EXPIRED_NOTICE = "session-expired";

export function hasSessionExpiredNotice(state: unknown): boolean {
  return isRecord(state) && state.notice === SESSION_EXPIRED_NOTICE;
}

export function getSafeReturnPath(state: unknown, fallback = HOME_PATH): string {
  if (!isRecord(state) || typeof state.from !== "string") {
    return fallback;
  }

  const path = state.from;
  const isSafeInternalPath = path.startsWith("/") && !path.startsWith("//") && path !== LOGIN_PATH;
  return isSafeInternalPath ? path : fallback;
}
