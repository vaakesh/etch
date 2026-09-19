import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  clearSessionCache,
  createSessionCacheKey,
  deleteSessionCacheEntry,
  ensureSessionCache,
  getCurrentSessionCacheScope,
  getSessionCacheEntry,
  isSessionCacheScopeActive,
  setSessionCacheEntry,
  startSessionCache,
  subscribeToSessionCacheScope,
} from "./session-cache";

const CACHE_KEY = createSessionCacheKey<{ owner: string }>("test.personal-data");

describe("session cache", () => {
  beforeEach(() => {
    clearSessionCache();
  });

  it("isolates entries by user and session revision", () => {
    const firstScope = startSessionCache("user-a");
    expect(setSessionCacheEntry(firstScope, CACHE_KEY, { owner: "user-a" })).toBe(true);
    expect(getSessionCacheEntry(firstScope, CACHE_KEY)).toEqual({ owner: "user-a" });

    const secondScope = startSessionCache("user-b");

    expect(secondScope.key).toBe(`user-b:${secondScope.sessionRevision}`);
    expect(secondScope.sessionRevision).toBeGreaterThan(firstScope.sessionRevision);
    expect(getSessionCacheEntry(secondScope, CACHE_KEY)).toBeUndefined();
    expect(getSessionCacheEntry(firstScope, CACHE_KEY)).toBeUndefined();
  });

  it("rejects late writes captured by an obsolete session", () => {
    const staleScope = startSessionCache("user-a");
    clearSessionCache();
    const activeScope = startSessionCache("user-b");

    expect(setSessionCacheEntry(staleScope, CACHE_KEY, { owner: "user-a" })).toBe(false);
    expect(deleteSessionCacheEntry(staleScope, CACHE_KEY)).toBe(false);
    expect(getSessionCacheEntry(activeScope, CACHE_KEY)).toBeUndefined();
  });

  it("starts with an empty revision after signing in again as the same user", () => {
    const firstScope = startSessionCache("user-a");
    setSessionCacheEntry(firstScope, CACHE_KEY, { owner: "first session" });

    const secondScope = startSessionCache("user-a");

    expect(secondScope.sessionRevision).toBeGreaterThan(firstScope.sessionRevision);
    expect(getSessionCacheEntry(secondScope, CACHE_KEY)).toBeUndefined();
    expect(setSessionCacheEntry(firstScope, CACHE_KEY, { owner: "late response" })).toBe(false);
  });

  it("clears all entries and notifies scope subscribers", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeToSessionCacheScope(listener);
    const scope = startSessionCache("user-a");
    setSessionCacheEntry(scope, CACHE_KEY, { owner: "user-a" });

    clearSessionCache();

    expect(getCurrentSessionCacheScope()).toBeNull();
    expect(isSessionCacheScopeActive(scope)).toBe(false);
    expect(listener).toHaveBeenCalledTimes(2);
    unsubscribe();
  });

  it("keeps the current revision when ensuring the same authenticated user", () => {
    const scope = startSessionCache("user-a");

    expect(ensureSessionCache("user-a")).toBe(scope);
    expect(ensureSessionCache("user-b").sessionRevision).toBeGreaterThan(scope.sessionRevision);
  });
});
