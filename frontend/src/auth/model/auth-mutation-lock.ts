const LOCK_NAME = "etch-auth-mutation";

let localMutationTail: Promise<void> = Promise.resolve();

function createAbortError(signal: AbortSignal): unknown {
  return signal.reason ?? new DOMException("The operation was aborted.", "AbortError");
}

function raceWithAbort<T>(operation: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) {
    return operation;
  }

  if (signal.aborted) {
    return Promise.reject(createAbortError(signal));
  }

  return new Promise<T>((resolve, reject) => {
    const handleAbort = () => reject(createAbortError(signal));
    const cleanup = () => signal.removeEventListener("abort", handleAbort);

    signal.addEventListener("abort", handleAbort, { once: true });
    operation.then(
      (value) => {
        cleanup();
        resolve(value);
      },
      (error: unknown) => {
        cleanup();
        reject(error);
      },
    );
  });
}

function withLocalMutationLock<T>(operation: () => Promise<T>, signal?: AbortSignal): Promise<T> {
  const scheduledOperation = localMutationTail.then(async () => {
    if (signal?.aborted) {
      throw createAbortError(signal);
    }
    return operation();
  });

  localMutationTail = scheduledOperation.then(
    () => undefined,
    () => undefined,
  );

  return raceWithAbort(scheduledOperation, signal);
}

export function withAuthMutationLock<T>(
  operation: () => Promise<T>,
  signal?: AbortSignal,
): Promise<T> {
  if (typeof navigator !== "undefined" && navigator.locks) {
    return navigator.locks.request(LOCK_NAME, { mode: "exclusive", signal }, async () =>
      operation(),
    );
  }

  return withLocalMutationLock(operation, signal);
}
