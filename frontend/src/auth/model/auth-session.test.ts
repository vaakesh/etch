import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/api-error";
import {
  clearSessionCache,
  createSessionCacheKey,
  getCurrentSessionCacheScope,
  getSessionCacheEntry,
  setSessionCacheEntry,
  startSessionCache,
} from "./session-cache";

const configureSessionMock = vi.hoisted(() => vi.fn());

vi.mock("../../api", () => ({
  apiClient: { configureSession: configureSessionMock },
}));

vi.mock("../api/auth-api", () => ({
  refreshSessionRequest: vi.fn(),
}));

vi.mock("./auth-mutation-lock", () => ({
  withAuthMutationLock: vi.fn(),
}));

import { handleUnauthorizedSession, setUnauthorizedListener } from "./auth-session";

const PERSONAL_ENTRY = createSessionCacheKey<string>("test.final-401");

describe("auth session cache invalidation", () => {
  beforeEach(() => {
    clearSessionCache();
    setUnauthorizedListener(null);
  });

  it("clears personal data before notifying about a final unauthorized response", () => {
    const scope = startSessionCache("user-a");
    setSessionCacheEntry(scope, PERSONAL_ENTRY, "private value");
    const listener = vi.fn(() => {
      expect(getCurrentSessionCacheScope()).toBeNull();
      expect(getSessionCacheEntry(scope, PERSONAL_ENTRY)).toBeUndefined();
    });
    setUnauthorizedListener(listener);
    const error = new ApiError({ status: 401, message: "Session expired" });
    handleUnauthorizedSession(error);

    expect(listener).toHaveBeenCalledWith(error);
    expect(getCurrentSessionCacheScope()).toBeNull();
  });
});
