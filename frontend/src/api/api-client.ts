import { ApiError, isApiError } from "./api-error";
import type {
  ApiClientConfig,
  ApiRequestOptions,
  ApiSessionConfig,
  QueryParams,
} from "./api-types";

const JSON_CONTENT_TYPE = "application/json";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function buildUrl(baseUrl: string, path: string, query?: QueryParams): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${baseUrl}${normalizedPath}`;

  if (!query) {
    return url;
  }

  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(query)) {
    if (value === null || value === undefined) {
      continue;
    }

    const values = Array.isArray(value) ? value : [value];
    for (const item of values) {
      searchParams.append(key, String(item));
    }
  }

  const search = searchParams.toString();
  if (!search) {
    return url;
  }

  return `${url}${url.includes("?") ? "&" : "?"}${search}`;
}

function isDirectRequestBody(
  value: unknown,
): value is string | FormData | URLSearchParams | Blob | ArrayBuffer {
  return (
    typeof value === "string" ||
    value instanceof FormData ||
    value instanceof URLSearchParams ||
    value instanceof Blob ||
    value instanceof ArrayBuffer
  );
}

function prepareBody(body: unknown, headers: Headers): BodyInit | undefined {
  if (body === undefined) {
    return undefined;
  }

  if (isDirectRequestBody(body)) {
    return body;
  }

  let serializedBody: string | undefined;
  try {
    serializedBody = JSON.stringify(body);
  } catch (error) {
    throw new ApiError({
      status: 0,
      code: "REQUEST_SERIALIZATION_FAILED",
      message: "Request body could not be serialized.",
      cause: error,
    });
  }

  if (serializedBody === undefined) {
    throw new ApiError({
      status: 0,
      code: "REQUEST_SERIALIZATION_FAILED",
      message: "Request body could not be serialized.",
    });
  }

  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", JSON_CONTENT_TYPE);
  }

  return serializedBody;
}

function createAbortError(cause?: unknown): ApiError {
  return new ApiError({
    status: 0,
    code: "REQUEST_ABORTED",
    message: "The request was cancelled.",
    cause,
  });
}

function normalizeTransportError(error: unknown): ApiError {
  if (isApiError(error)) {
    return error;
  }

  if (error instanceof DOMException && error.name === "AbortError") {
    return createAbortError(error);
  }

  return new ApiError({
    status: 0,
    code: "NETWORK_ERROR",
    message: "The server could not be reached. Check your connection and try again.",
    cause: error,
  });
}

function getErrorData(data: unknown, fallbackMessage: string) {
  if (typeof data === "string" && data.trim()) {
    return { message: data };
  }

  if (!isRecord(data)) {
    return { message: fallbackMessage };
  }

  const detail = data.detail;
  const message =
    (typeof data.message === "string" && data.message) ||
    (typeof detail === "string" && detail) ||
    fallbackMessage;
  const code = typeof data.code === "string" ? data.code : undefined;
  const details = data.details ?? (typeof detail === "string" ? undefined : detail);

  return { message, code, details };
}

async function parseResponse<TResponse>(response: Response): Promise<TResponse> {
  if (response.status === 204 || response.status === 205) {
    return undefined as TResponse;
  }

  const rawBody = await response.text();
  const contentType = response.headers.get("Content-Type")?.toLowerCase() ?? "";
  const isJson = contentType.includes(JSON_CONTENT_TYPE) || contentType.includes("+json");

  let data: unknown = rawBody;
  if (rawBody && isJson) {
    try {
      data = JSON.parse(rawBody) as unknown;
    } catch (error) {
      throw new ApiError({
        status: response.status,
        code: "INVALID_JSON_RESPONSE",
        message: "The server returned invalid JSON.",
        details: rawBody,
        cause: error,
      });
    }
  } else if (!rawBody) {
    data = undefined;
  }

  if (!response.ok) {
    const errorData = getErrorData(data, response.statusText || "The API request failed.");
    throw new ApiError({
      status: response.status,
      message: errorData.message,
      code: errorData.code,
      details: errorData.details,
    });
  }

  return data as TResponse;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchFn: typeof fetch;
  private sessionConfig: ApiSessionConfig | null = null;
  private refreshPromise: Promise<void> | null = null;
  private refreshController: AbortController | null = null;
  private sessionRevision = 0;
  private credentialRevision = 0;

  constructor(config: ApiClientConfig) {
    this.baseUrl = config.baseUrl;
    this.fetchFn = config.fetchFn ?? globalThis.fetch.bind(globalThis);
  }

  configureSession(config: ApiSessionConfig): void {
    this.sessionConfig = config;
  }

  startSession(): void {
    this.advanceSession();
    this.credentialRevision += 1;
  }

  invalidateSession(): void {
    this.advanceSession();
  }

  refreshSession(signal?: AbortSignal | null): Promise<void> {
    if (signal?.aborted) {
      return Promise.reject(createAbortError(signal.reason));
    }

    if (!this.refreshPromise) {
      if (!this.sessionConfig) {
        return Promise.reject(
          new ApiError({
            status: 401,
            code: "REFRESH_NOT_CONFIGURED",
            message: "Session refresh is not configured.",
          }),
        );
      }

      const revision = this.sessionRevision;
      const controller = new AbortController();
      this.refreshController = controller;

      const refreshTask = this.runRefresh(revision, controller);
      const trackedPromise = refreshTask.finally(() => {
        if (this.refreshPromise === trackedPromise) {
          this.refreshPromise = null;
          this.refreshController = null;
        }
      });
      this.refreshPromise = trackedPromise;
    }

    return this.waitForRefresh(this.refreshPromise, signal);
  }

  async request<TResponse, TBody = unknown>(
    path: string,
    options: ApiRequestOptions<TBody> = {},
  ): Promise<TResponse> {
    return this.executeRequest<TResponse, TBody>(path, options, false);
  }

  private async executeRequest<TResponse, TBody>(
    path: string,
    options: ApiRequestOptions<TBody>,
    hasRetried: boolean,
  ): Promise<TResponse> {
    const requestRevision = this.sessionRevision;
    const requestCredentialRevision = this.credentialRevision;
    const response = await this.sendRequest(path, options);
    const canRetryUnauthorized =
      response.status === 401 &&
      options.auth !== false &&
      options.retryOnUnauthorized !== false &&
      !hasRetried;
    const hasNewerCredentials = requestCredentialRevision !== this.credentialRevision;

    if (canRetryUnauthorized && hasNewerCredentials && requestRevision === this.sessionRevision) {
      return this.executeRequest<TResponse, TBody>(path, options, true);
    }

    if (canRetryUnauthorized) {
      try {
        await this.refreshSession(options.signal);
      } catch (error) {
        const apiError = normalizeTransportError(error);
        if (apiError.code !== "REQUEST_ABORTED" && requestRevision === this.sessionRevision) {
          this.expireSession(apiError);
        }
        throw apiError;
      }

      if (requestRevision !== this.sessionRevision) {
        throw new ApiError({
          status: 401,
          code: "SESSION_INVALIDATED",
          message: "The session ended before the request could be retried.",
        });
      }

      return this.executeRequest<TResponse, TBody>(path, options, true);
    }

    try {
      return await parseResponse<TResponse>(response);
    } catch (error) {
      const apiError = options.signal?.aborted
        ? createAbortError(options.signal.reason)
        : normalizeTransportError(error);
      if (
        hasRetried &&
        response.status === 401 &&
        options.auth !== false &&
        requestRevision === this.sessionRevision &&
        apiError.status === 401
      ) {
        this.expireSession(apiError);
      }
      throw apiError;
    }
  }

  private async sendRequest<TBody>(
    path: string,
    options: ApiRequestOptions<TBody>,
  ): Promise<Response> {
    const {
      auth: _auth = true,
      body,
      headers: inputHeaders,
      method = "GET",
      query,
      retryOnUnauthorized: _retryOnUnauthorized,
      ...requestInit
    } = options;
    void _auth;
    void _retryOnUnauthorized;
    const headers = new Headers(inputHeaders);

    try {
      return await this.fetchFn(buildUrl(this.baseUrl, path, query), {
        ...requestInit,
        body: prepareBody(body, headers),
        credentials: requestInit.credentials ?? "include",
        headers,
        method,
      });
    } catch (error) {
      if (requestInit.signal?.aborted) {
        throw createAbortError(requestInit.signal.reason);
      }
      throw normalizeTransportError(error);
    }
  }

  private async runRefresh(revision: number, controller: AbortController): Promise<void> {
    if (!this.sessionConfig) {
      return;
    }

    try {
      await this.sessionConfig.refresh(controller.signal);

      if (revision !== this.sessionRevision) {
        throw new ApiError({
          status: 401,
          code: "SESSION_INVALIDATED",
          message: "The session ended while it was being refreshed.",
        });
      }

      this.credentialRevision += 1;
    } catch (error) {
      if (revision !== this.sessionRevision) {
        throw new ApiError({
          status: 401,
          code: "SESSION_INVALIDATED",
          message: "The session ended while it was being refreshed.",
          cause: error,
        });
      }

      const apiError = normalizeTransportError(error);

      throw apiError;
    }
  }

  private waitForRefresh(
    refreshPromise: Promise<void>,
    signal?: AbortSignal | null,
  ): Promise<void> {
    if (!signal) {
      return refreshPromise;
    }

    if (signal.aborted) {
      return Promise.reject(createAbortError(signal.reason));
    }

    return new Promise<void>((resolve, reject) => {
      const handleAbort = () => {
        reject(createAbortError(signal.reason));
      };
      const cleanup = () => {
        signal.removeEventListener("abort", handleAbort);
      };

      signal.addEventListener("abort", handleAbort, { once: true });
      refreshPromise.then(
        () => {
          cleanup();
          resolve();
        },
        (error: unknown) => {
          cleanup();
          reject(error);
        },
      );
    });
  }

  private advanceSession(): void {
    this.sessionRevision += 1;
    this.refreshController?.abort();
    this.refreshController = null;
    this.refreshPromise = null;
  }

  private expireSession(error: ApiError): void {
    this.advanceSession();
    this.sessionConfig?.onUnauthorized?.(error);
  }
}
