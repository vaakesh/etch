export const LIBRARY_PATH = "/library";

export const LIBRARY_CREATE_DECK_NAVIGATION_STATE = {
  libraryAction: "create-deck",
} as const;

export function shouldOpenDeckCreator(state: unknown): boolean {
  return (
    typeof state === "object" &&
    state !== null &&
    "libraryAction" in state &&
    state.libraryAction === LIBRARY_CREATE_DECK_NAVIGATION_STATE.libraryAction
  );
}
