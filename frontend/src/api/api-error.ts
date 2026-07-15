export interface ApiErrorOptions {
  status: number;
  message: string;
  code?: string;
  details?: unknown;
  cause?: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly details?: unknown;

  constructor(options: ApiErrorOptions) {
    super(options.message, { cause: options.cause });
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code;
    this.details = options.details;
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
