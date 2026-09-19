export const DECK_DETAILS_ROUTE_PATH = "/decks/:deck_uuid";

export type DeckDetailsReturnTarget = "catalog" | "home" | "library" | "practice" | "profile";

interface DeckDetailsNavigationState {
  deckDetailsReturnTarget: DeckDetailsReturnTarget;
  profileUsername?: string;
}

export function createDeckDetailsNavigationState(
  target: DeckDetailsReturnTarget,
  profileUsername?: string,
): DeckDetailsNavigationState {
  return {
    deckDetailsReturnTarget: target,
    ...(target === "profile" && profileUsername ? { profileUsername } : {}),
  };
}

export function getDeckDetailsPath(deckUuid: string): string {
  return `/decks/${encodeURIComponent(deckUuid)}`;
}

export function getDeckDetailsReturnTarget(state: unknown): DeckDetailsReturnTarget | null {
  if (typeof state !== "object" || state === null) {
    return null;
  }

  const target = (state as Record<string, unknown>).deckDetailsReturnTarget;
  return target === "catalog" ||
    target === "home" ||
    target === "library" ||
    target === "practice" ||
    target === "profile"
    ? target
    : null;
}

export function getDeckDetailsProfilePath(state: unknown): string | null {
  if (typeof state !== "object" || state === null) {
    return null;
  }

  const profileUsername = (state as Record<string, unknown>).profileUsername;
  return typeof profileUsername === "string" && profileUsername.length > 0
    ? `/users/${encodeURIComponent(profileUsername)}`
    : null;
}
