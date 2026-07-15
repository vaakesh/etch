export type AuthSessionEvent =
  { type: "signed-in"; sequence: number } | { type: "signed-out"; sequence: number };

export type AuthSessionEventInput = { type: "signed-in" } | { type: "signed-out" };

type AuthSessionEventListener = (event: AuthSessionEvent) => void;

const CHANNEL_NAME = "etch-auth-session";
const SEQUENCE_KEY = "etch-auth-session-sequence";
const listeners = new Set<AuthSessionEventListener>();
const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(CHANNEL_NAME);
let fallbackSequence = 0;

function isAuthSessionEvent(value: unknown): value is AuthSessionEvent {
  if (
    typeof value !== "object" ||
    value === null ||
    !("type" in value) ||
    !("sequence" in value) ||
    typeof value.sequence !== "number" ||
    !Number.isSafeInteger(value.sequence) ||
    value.sequence < 0
  ) {
    return false;
  }

  if (value.type === "signed-out") {
    return true;
  }

  return value.type === "signed-in";
}

channel?.addEventListener("message", (message: MessageEvent<unknown>) => {
  if (!isAuthSessionEvent(message.data)) {
    return;
  }

  for (const listener of listeners) {
    listener(message.data);
  }
});

export function getCurrentAuthSessionSequence(): number {
  if (typeof localStorage === "undefined") {
    return fallbackSequence;
  }

  try {
    const storedSequence = Number(localStorage.getItem(SEQUENCE_KEY));
    return Number.isSafeInteger(storedSequence) && storedSequence >= 0 ? storedSequence : 0;
  } catch {
    return fallbackSequence;
  }
}

function getNextSequence(): number {
  const sequence = Math.max(fallbackSequence, getCurrentAuthSessionSequence()) + 1;
  fallbackSequence = sequence;

  try {
    localStorage.setItem(SEQUENCE_KEY, String(sequence));
  } catch {
    // The in-memory sequence still orders events when storage is unavailable.
  }

  return sequence;
}

export function publishAuthSessionEvent(event: AuthSessionEventInput): number {
  const sequence = getNextSequence();
  channel?.postMessage({ ...event, sequence } satisfies AuthSessionEvent);
  return sequence;
}

export function subscribeToAuthSessionEvents(listener: AuthSessionEventListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
