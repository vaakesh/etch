import { solveChallenge } from "altcha-lib";
import { deriveKey } from "altcha-lib/algorithms/web/pbkdf2";
import type { Challenge } from "altcha-lib/types";
import { AUTH_ENDPOINTS, apiFetch } from "../../api";
import { AuthContractError } from "./auth-contract";

export const CAPTCHA_HEADER = "X-Altcha";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

// The challenge goes back to the backend untouched: its signature covers every parameter.
function isChallenge(payload: unknown): payload is Challenge {
  if (!isRecord(payload) || typeof payload.signature !== "string") {
    return false;
  }

  const { parameters } = payload;
  return (
    isRecord(parameters) &&
    typeof parameters.algorithm === "string" &&
    typeof parameters.nonce === "string" &&
    typeof parameters.salt === "string" &&
    typeof parameters.keyPrefix === "string" &&
    typeof parameters.cost === "number" &&
    typeof parameters.keyLength === "number"
  );
}

/**
 * Proof of work for one captcha-protected request: `GET /auth/challenge`, then a counter search.
 * The backend accepts a solution once, so every protected request needs its own call.
 */
export async function solveCaptcha(signal?: AbortSignal): Promise<string> {
  const challenge = await apiFetch<unknown>(AUTH_ENDPOINTS.challenge, {
    auth: false,
    retryOnUnauthorized: false,
    signal,
  });
  if (!isChallenge(challenge)) {
    throw new AuthContractError(
      "INVALID_CAPTCHA_CHALLENGE",
      "The backend returned an unexpected captcha challenge shape.",
    );
  }

  signal?.throwIfAborted();
  const controller = new AbortController();
  const abort = (): void => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });

  try {
    const solution = await solveChallenge({ challenge, controller, deriveKey });
    if (solution === null) {
      // A cancelled search is the caller's abort, not a captcha failure.
      signal?.throwIfAborted();
      throw new AuthContractError("CAPTCHA_NOT_SOLVED", "The captcha challenge was not solved.");
    }
    return btoa(JSON.stringify({ challenge, solution }));
  } finally {
    signal?.removeEventListener("abort", abort);
  }
}
