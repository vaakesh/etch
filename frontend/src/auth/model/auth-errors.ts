import { isApiError } from "../../api";

const REJECTED_SESSION_STATUSES = new Set([401, 403, 404]);

export function isAuthSessionRejected(error: unknown): boolean {
  return isApiError(error) && REJECTED_SESSION_STATUSES.has(error.status);
}
