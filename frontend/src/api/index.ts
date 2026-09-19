import { ApiClient } from "./api-client";
import type { ApiRequestOptions } from "./api-types";
import { env } from "./env";

export { ApiError, isApiError } from "./api-error";
export {
  API_ERROR_CODES,
  hasAnyApiErrorCode,
  hasApiErrorCode,
  type ApiErrorCode,
} from "./error-codes";
export type { ApiRequestOptions } from "./api-types";
export { AUTH_ENDPOINTS, USER_ENDPOINTS } from "./endpoints";

export const apiClient = new ApiClient({
  baseUrl: env.apiBaseUrl,
});

export function apiFetch<TResponse, TBody = unknown>(
  path: string,
  options?: ApiRequestOptions<TBody>,
): Promise<TResponse> {
  return apiClient.request<TResponse, TBody>(path, options);
}
