import { createChallenge, verifySolution } from "altcha-lib";
import { deriveKey } from "altcha-lib/algorithms/pbkdf2";
import type { Challenge } from "altcha-lib/types";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }));

vi.mock("../../api", () => ({
  AUTH_ENDPOINTS: { challenge: "/auth/challenge" },
  apiFetch,
}));

import { solveCaptcha } from "./captcha-api";

const HMAC_SECRET = "test-hmac-key";

function issueChallenge(): Promise<Challenge> {
  return createChallenge({
    algorithm: "PBKDF2/SHA-256",
    cost: 1,
    counter: 3,
    deriveKey,
    hmacSignatureSecret: HMAC_SECRET,
  });
}

describe("solveCaptcha", () => {
  beforeEach(() => {
    apiFetch.mockReset();
  });

  it("requests a challenge without the session and returns a payload the backend verifies", async () => {
    const challenge = await issueChallenge();
    const signal = new AbortController().signal;
    apiFetch.mockResolvedValue(challenge);

    const payload = await solveCaptcha(signal);

    expect(apiFetch).toHaveBeenCalledWith("/auth/challenge", {
      auth: false,
      retryOnUnauthorized: false,
      signal,
    });
    const decoded: unknown = JSON.parse(atob(payload));
    expect(decoded).toEqual({
      challenge,
      solution: expect.objectContaining({ counter: 3 }),
    });
    const { solution } = decoded as { solution: { counter: number; derivedKey: string } };
    const result = await verifySolution({
      challenge,
      solution,
      deriveKey,
      hmacSignatureSecret: HMAC_SECRET,
    });
    expect(result.verified).toBe(true);
  });

  it.each([
    ["a non-object response", null],
    ["a challenge without a signature", { parameters: {} }],
    ["a challenge without parameters", { signature: "signature" }],
    [
      "parameters without a nonce",
      {
        parameters: {
          algorithm: "PBKDF2/SHA-256",
          cost: 1,
          keyLength: 32,
          keyPrefix: "00",
          salt: "00",
        },
        signature: "signature",
      },
    ],
  ])("rejects %s as a contract error", async (_name, response) => {
    apiFetch.mockResolvedValue(response);

    await expect(solveCaptcha()).rejects.toMatchObject({
      code: "INVALID_CAPTCHA_CHALLENGE",
      status: 0,
    });
  });

  it("stops with the caller's abort reason when the request is cancelled", async () => {
    const controller = new AbortController();
    apiFetch.mockImplementation(async () => {
      controller.abort(new Error("cancelled by caller"));
      return issueChallenge();
    });

    await expect(solveCaptcha(controller.signal)).rejects.toThrow("cancelled by caller");
  });
});
