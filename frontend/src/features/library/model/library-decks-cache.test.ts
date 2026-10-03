import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../../api";
import { clearSessionCache, startSessionCache } from "../../../auth/model/session-cache";
import { setCatalogDeckSaved } from "../../catalog/api/catalog-api";
import {
  getCachedLibraryDecks,
  setCachedLibraryDecks,
  subscribeToLibraryDeckSaveChanges,
} from "./library-decks-cache";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const OTHER_DECK_UUID = "f9b7ced5-fbea-4741-82fd-33ea144dab7c";
const USER_UUID = "d2f61c35-11d0-489e-837d-3845418ba39e";

function cacheLibrary(onlyFavourites = false): void {
  setCachedLibraryDecks({
    currentUserUuid: USER_UUID,
    onlyFavourites,
    state: {
      searchQuery: "",
      status: "success",
      decks: [DECK_UUID, OTHER_DECK_UUID].map((uuid) => ({
        uuid,
        ownerUuid: "aaa61c35-11d0-489e-837d-3845418ba39e",
        ownerUsername: "deck-owner",
        title: "Saved deck",
        description: null,
        totalWordsCount: 10,
        savesCount: 12,
        accuracy: 75,
        isFavourite: true,
        updatedAt: null,
        cards: [],
      })),
      nextCursor: "next-page",
      hasMore: true,
      error: null,
      isLoadingMore: false,
      loadMoreError: null,
      favouriteUpdatingDeckUuids: [DECK_UUID, OTHER_DECK_UUID],
      favouriteErrors: { [DECK_UUID]: new Error("Previous favourite error") },
      deletingDeckUuids: [DECK_UUID],
      deleteErrors: { [DECK_UUID]: new Error("Previous delete error") },
    },
  });
}

describe("library state after catalog save changes", () => {
  const onSaveChange = vi.fn();
  let unsubscribe: () => void;

  beforeEach(() => {
    startSessionCache(USER_UUID);
    vi.mocked(apiFetch).mockReset();
    onSaveChange.mockReset();
    cacheLibrary();
    unsubscribe = subscribeToLibraryDeckSaveChanges(onSaveChange);
  });

  afterEach(() => {
    unsubscribe();
    setCachedLibraryDecks(null);
    clearSessionCache();
  });

  it.each([false, true])(
    "removes an unsaved favourite from cached onlyFavourites=%s",
    async (onlyFavourites) => {
      cacheLibrary(onlyFavourites);
      const previousCache = getCachedLibraryDecks();
      vi.mocked(apiFetch).mockResolvedValue(undefined);

      await setCatalogDeckSaved(DECK_UUID, false);

      expect(apiFetch).toHaveBeenCalledWith(`/decks/${DECK_UUID}/unsave`, {
        method: "POST",
        signal: undefined,
      });
      expect(getCachedLibraryDecks()).toMatchObject({
        onlyFavourites,
        state: {
          decks: [{ uuid: OTHER_DECK_UUID, isFavourite: true, accuracy: 75 }],
          nextCursor: "next-page",
          hasMore: true,
          favouriteUpdatingDeckUuids: [OTHER_DECK_UUID],
          favouriteErrors: {},
          deletingDeckUuids: [],
          deleteErrors: {},
        },
      });
      expect(getCachedLibraryDecks()?.state.decks).toHaveLength(1);
      expect(previousCache?.state.decks).toHaveLength(2);
      expect(onSaveChange).toHaveBeenCalledOnce();
    },
  );

  it("keeps favourites while unsave is pending and when it fails", async () => {
    const previousCache = getCachedLibraryDecks();
    const error = new Error("Unsave failed");
    let rejectRequest!: (reason: Error) => void;
    vi.mocked(apiFetch).mockReturnValue(
      new Promise((_, reject) => {
        rejectRequest = reject;
      }),
    );

    const request = setCatalogDeckSaved(DECK_UUID, false);

    expect(getCachedLibraryDecks()).toBe(previousCache);
    expect(onSaveChange).not.toHaveBeenCalled();
    rejectRequest(error);
    await expect(request).rejects.toBe(error);
    expect(getCachedLibraryDecks()).toBe(previousCache);
    expect(onSaveChange).not.toHaveBeenCalled();
  });

  it("reloads the library after saving the deck again", async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    await setCatalogDeckSaved(DECK_UUID, false);

    await setCatalogDeckSaved(DECK_UUID, true);

    expect(getCachedLibraryDecks()).toBeNull();
    expect(onSaveChange).toHaveBeenCalledTimes(2);
  });

  it("notifies mounted lists even without a cached library and unsubscribes on unmount", async () => {
    setCachedLibraryDecks(null);
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    await setCatalogDeckSaved(DECK_UUID, false);
    expect(onSaveChange).toHaveBeenCalledOnce();

    unsubscribe();
    await setCatalogDeckSaved(DECK_UUID, false);
    expect(onSaveChange).toHaveBeenCalledOnce();
  });
});
