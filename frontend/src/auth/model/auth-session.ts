import { apiClient } from "../../api";
import type { ApiError } from "../../api";
import { refreshSessionRequest } from "../api/auth-api";
import { withAuthMutationLock } from "./auth-mutation-lock";

type UnauthorizedListener = (error: ApiError) => void;

let unauthorizedListener: UnauthorizedListener | null = null;

apiClient.configureSession({
  refresh: (signal) => withAuthMutationLock(() => refreshSessionRequest(signal), signal),
  onUnauthorized: (error) => unauthorizedListener?.(error),
});

export function setUnauthorizedListener(listener: UnauthorizedListener | null): void {
  unauthorizedListener = listener;
}
