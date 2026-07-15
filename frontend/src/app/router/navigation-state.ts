function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export const LOGIN_PATH = "/login";
export const DASHBOARD_PATH = "/dashboard";

export function getSafeReturnPath(state: unknown, fallback = "/"): string {
  if (!isRecord(state) || typeof state.from !== "string") {
    return fallback;
  }

  const path = state.from;
  const isSafeInternalPath = path.startsWith("/") && !path.startsWith("//") && path !== LOGIN_PATH;
  return isSafeInternalPath ? path : fallback;
}
