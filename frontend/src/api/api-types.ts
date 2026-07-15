export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type QueryPrimitive = string | number | boolean;
export type QueryValue = QueryPrimitive | readonly QueryPrimitive[] | null | undefined;
export type QueryParams = Readonly<Record<string, QueryValue>>;

export interface ApiRequestOptions<TBody = unknown> extends Omit<
  RequestInit,
  "body" | "headers" | "method"
> {
  method?: HttpMethod;
  body?: TBody;
  headers?: HeadersInit;
  query?: QueryParams;
  auth?: boolean;
  retryOnUnauthorized?: boolean;
}

export type SessionRefreshHandler = (signal: AbortSignal) => Promise<void>;
export type UnauthorizedHandler = (error: import("./api-error").ApiError) => void;

export interface ApiSessionConfig {
  refresh: SessionRefreshHandler;
  onUnauthorized?: UnauthorizedHandler;
}

export interface ApiClientConfig {
  baseUrl: string;
  fetchFn?: typeof fetch;
}
