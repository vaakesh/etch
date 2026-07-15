import { afterEach, describe, expect, it, vi } from "vitest";
import { withAuthMutationLock } from "./auth-mutation-lock";

function deferred<T>() {
  let resolvePromise!: (value: T | PromiseLike<T>) => void;
  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve;
  });

  return { promise, resolve: resolvePromise };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("withAuthMutationLock", () => {
  it("runs fallback mutations sequentially", async () => {
    vi.stubGlobal("navigator", {});
    const firstGate = deferred<void>();
    const events: string[] = [];

    const first = withAuthMutationLock(async () => {
      events.push("first:start");
      await firstGate.promise;
      events.push("first:end");
    });
    const second = withAuthMutationLock(async () => {
      events.push("second:start");
    });

    await Promise.resolve();
    expect(events).toEqual(["first:start"]);

    firstGate.resolve();
    await Promise.all([first, second]);

    expect(events).toEqual(["first:start", "first:end", "second:start"]);
  });
});
