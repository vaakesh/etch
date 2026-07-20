import { apiFetch } from "../../../api";
import { parseLibraryDeckPage } from "../model/library-contract";
import type { LibraryDeckPage } from "../model/library-types";

const LIBRARY_DECKS_PATH = "/bff/decks";

export async function getLibraryDeckPage(
  cursor: string | null,
  signal?: AbortSignal,
): Promise<LibraryDeckPage> {
  const payload = await apiFetch<unknown>(LIBRARY_DECKS_PATH, {
    query: { cursor },
    signal,
  });

  return parseLibraryDeckPage(payload);
}
