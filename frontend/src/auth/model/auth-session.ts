import { apiClient } from "../../api";
import type { ApiError } from "../../api";
import { refreshSessionRequest } from "../api/auth-api";
import { withAuthMutationLock } from "./auth-mutation-lock";
import { clearSessionCache } from "./session-cache";

type UnauthorizedListener = (error: ApiError) => void;

let unauthorizedListener: UnauthorizedListener | null = null;

export function handleUnauthorizedSession(error: ApiError): void {
  clearSessionCache();
  unauthorizedListener?.(error);
}

apiClient.configureSession({
  refresh: (signal) => withAuthMutationLock(() => refreshSessionRequest(signal), signal),
  onUnauthorized: handleUnauthorizedSession,
});

export function setUnauthorizedListener(listener: UnauthorizedListener | null): void {
  unauthorizedListener = listener;
}
