import type { Request } from "@playwright/test";
import { createChallenge, verifySolution } from "altcha-lib";
import { deriveKey } from "altcha-lib/algorithms/pbkdf2";
import type { Challenge, Solution } from "altcha-lib/types";
import type { CurrentUserResponse } from "../data/builders";
import type { BrowserDiagnostics } from "../fixtures/base-test";
import type { ApiMockRouter } from "./api-router";

const CAPTCHA_HMAC_SECRET = "e2e-captcha-key";

export interface LoginCredentials {
  username: string;
  password: string;
}

// Error envelopes: backend/app/exception_handlers.py.
export const AUTH_ERRORS = {
  invalidLoginCredentials: {
    status: 404,
    json: { code: "INVALID_LOGIN_CREDENTIALS", message: "Invalid login credentials" },
  },
  captchaInvalid: {
    status: 403,
    json: { code: "CAPTCHA_INVALID", message: "Captcha verification failed" },
  },
  usernameAlreadyExists: {
    status: 409,
    json: { code: "USERNAME_ALREADY_EXISTS", message: "Username already exists" },
  },
  validation: {
    status: 422,
    json: { code: "VALIDATION_ERROR", message: "Validation error", details: [] },
  },
  rateLimit: {
    status: 429,
    json: { code: "RATE_LIMIT_EXCEEDED", message: "Rate limit exceeded" },
  },
  internal: {
    status: 500,
    json: { code: "INTERNAL_SERVER_ERROR", message: "Internal server error" },
  },
} as const;

/**
 * Cookie session model of one browser context: `GET /users/me` and `POST /auth/refresh` follow
 * the current user. Login/logout stay unhandled until a scenario arranges them explicitly.
 * `GET /auth/challenge` always issues a cheap real captcha; arranged login and registration
 * accept each solution once, like the backend.
 */
export class AuthMock {
  private user: CurrentUserResponse | null;
  private guestErrorsExpected = false;
  private readonly unusedCaptchas = new Set<string>();
  private readonly api: ApiMockRouter;
  private readonly diagnostics: BrowserDiagnostics;

  constructor(
    api: ApiMockRouter,
    diagnostics: BrowserDiagnostics,
    user: CurrentUserResponse | null,
  ) {
    this.api = api;
    this.diagnostics = diagnostics;
    this.user = user;
    if (!user) this.expectGuestErrors();

    api.on("GET", "/users/me", async ({ route }) => {
      await route.fulfill(
        this.user
          ? { json: this.user }
          : {
              status: 401,
              json: { code: "ACCESS_TOKEN_NOT_FOUND", message: "Access token not found" },
            },
      );
    });
    api.on("GET", "/auth/challenge", async ({ route }) => {
      const challenge = await createChallenge({
        algorithm: "PBKDF2/SHA-256",
        cost: 1,
        counter: 3,
        deriveKey,
        hmacSignatureSecret: CAPTCHA_HMAC_SECRET,
      });
      if (challenge.signature) this.unusedCaptchas.add(challenge.signature);
      await route.fulfill({ json: challenge });
    });
    api.on("POST", "/auth/refresh", async ({ route }) => {
      if (this.user) {
        // A valid session must not need a refresh unless the scenario arranges an expired token.
        api.unexpected.push("POST /api/auth/refresh (session is valid)");
        await route.abort("blockedbyclient");
        return;
      }
      await route.fulfill({
        status: 401,
        json: { code: "REFRESH_TOKEN_NOT_FOUND", message: "Refresh token not found" },
      });
    });
  }

  get currentUser(): CurrentUserResponse | null {
    return this.user;
  }

  /** `POST /auth/login`: 204 and a session for matching credentials, backend 404 otherwise. */
  allowLogin(
    credentials: LoginCredentials,
    user: CurrentUserResponse,
    options: { holdUntil?: Promise<void> } = {},
  ): void {
    this.api.on("POST", "/auth/login", async ({ route, request }) => {
      await options.holdUntil;
      if (!(await this.acceptCaptcha(request))) {
        await route.fulfill(AUTH_ERRORS.captchaInvalid);
        return;
      }
      const body = request.postDataJSON() as Partial<LoginCredentials> | null;
      if (body?.username !== credentials.username || body.password !== credentials.password) {
        await route.fulfill(AUTH_ERRORS.invalidLoginCredentials);
        return;
      }
      this.user = structuredClone(user);
      await route.fulfill({ status: 204 });
    });
  }

  /**
   * `POST /users/create`: 201 with the new account. The account can sign in afterwards with the
   * submitted credentials unless `enableLogin` is false (the scenario then arranges login itself).
   */
  allowRegistration(user: CurrentUserResponse, options: { enableLogin?: boolean } = {}): void {
    this.api.on("POST", "/users/create", async ({ route, request }) => {
      if (!(await this.acceptCaptcha(request))) {
        await route.fulfill(AUTH_ERRORS.captchaInvalid);
        return;
      }
      const body = request.postDataJSON() as LoginCredentials;
      if (options.enableLogin !== false) {
        this.allowLogin({ username: body.username, password: body.password }, user);
      }
      await route.fulfill({ status: 201, json: user });
    });
  }

  /** `POST /auth/logout`: ends the session; later bootstrap requests answer as for a guest. */
  allowLogout(options: { holdUntil?: Promise<void> } = {}): void {
    this.api.on("POST", "/auth/logout", async ({ route }) => {
      await options.holdUntil;
      this.signOut();
      await route.fulfill({ json: null });
    });
  }

  /** Server-side session loss without any request from the page. */
  signOut(): void {
    this.user = null;
    this.expectGuestErrors();
  }

  /** `X-Altcha` must carry a solved challenge issued by this mock and not used before. */
  private async acceptCaptcha(request: Request): Promise<boolean> {
    const header = request.headers()["x-altcha"];
    if (!header) return false;
    const { challenge, solution } = JSON.parse(atob(header)) as {
      challenge: Challenge;
      solution: Solution;
    };
    const result = await verifySolution({
      challenge,
      solution,
      deriveKey,
      hmacSignatureSecret: CAPTCHA_HMAC_SECRET,
    });
    return (
      result.verified &&
      challenge.signature !== undefined &&
      this.unusedCaptchas.delete(challenge.signature)
    );
  }

  private expectGuestErrors(): void {
    if (this.guestErrorsExpected) return;
    this.guestErrorsExpected = true;
    this.diagnostics.expectHttpError({
      method: "GET",
      pathname: "/api/users/me",
      status: 401,
      reason: "Guest bootstrap has no access cookie",
    });
    this.diagnostics.expectHttpError({
      method: "POST",
      pathname: "/api/auth/refresh",
      status: 401,
      reason: "Guest has no refresh cookie",
    });
  }
}
