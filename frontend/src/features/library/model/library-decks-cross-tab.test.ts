import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const NativeBroadcastChannel = globalThis.BroadcastChannel;
const channels: BroadcastChannel[] = [];
const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const USER_UUID = "d2f61c35-11d0-489e-837d-3845418ba39e";

async function openTab() {
  vi.resetModules();
  const tab = await import("./library-decks-cache");
  const { startSessionCache } = await import("../../../auth/model/session-cache");
  startSessionCache(USER_UUID);
  return tab;
}

function cacheFavourite(tab: Awaited<ReturnType<typeof openTab>>): void {
  tab.setCachedLibraryDecks({
    currentUserUuid: USER_UUID,
    onlyFavourites: true,
    state: {
      searchQuery: "",
      status: "success",
      decks: [
        {
          uuid: DECK_UUID,
          ownerUuid: "aaa61c35-11d0-489e-837d-3845418ba39e",
          ownerUsername: "deck-owner",
          title: "Saved favourite",
          description: null,
          totalWordsCount: 10,
          savesCount: 12,
          accuracy: 75,
          isFavourite: true,
          updatedAt: null,
          cards: [],
        },
      ],
      nextCursor: null,
      hasMore: false,
      error: null,
      isLoadingMore: false,
      loadMoreError: null,
      favouriteUpdatingDeckUuids: [],
      favouriteErrors: {},
      deletingDeckUuids: [],
      deleteErrors: {},
    },
  });
}

describe("deck saves across tabs", () => {
  beforeEach(() => {
    vi.stubGlobal("window", {});
    vi.stubGlobal(
      "BroadcastChannel",
      class extends NativeBroadcastChannel {
        constructor(name: string) {
          super(name);
          channels.push(this);
        }
      },
    );
  });

  afterEach(() => {
    channels.splice(0).forEach((channel) => channel.close());
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("refreshes the saved-decks tab after save, favourite, unsave, and save again", async () => {
    const catalogTab = await openTab();
    const libraryTab = await openTab();
    const catalogListener = vi.fn();
    const libraryListener = vi.fn();
    catalogTab.subscribeToLibraryDeckSaveChanges(catalogListener);
    libraryTab.subscribeToLibraryDeckSaveChanges(libraryListener);

    catalogTab.updateLibraryDeckSavedState(DECK_UUID, true);
    await vi.waitFor(() => expect(libraryListener).toHaveBeenCalledWith("remote"));

    cacheFavourite(libraryTab);
    catalogTab.updateLibraryDeckSavedState(DECK_UUID, false);
    await vi.waitFor(() => expect(libraryListener).toHaveBeenCalledTimes(2));
    expect(libraryTab.getCachedLibraryDecks()).toBeNull();

    catalogTab.updateLibraryDeckSavedState(DECK_UUID, true);
    await vi.waitFor(() => expect(libraryListener).toHaveBeenCalledTimes(3));
    expect(catalogListener.mock.calls).toEqual([["local"], ["local"], ["local"]]);
  });

  it("invalidates an unmounted tab's cache without needing a listener", async () => {
    const catalogTab = await openTab();
    const libraryTab = await openTab();
    cacheFavourite(libraryTab);

    catalogTab.updateLibraryDeckSavedState(DECK_UUID, false);

    await vi.waitFor(() => expect(libraryTab.getCachedLibraryDecks()).toBeNull());
  });

  it("ignores unrelated channel messages", async () => {
    const libraryTab = await openTab();
    cacheFavourite(libraryTab);
    const previousCache = libraryTab.getCachedLibraryDecks();
    channels[0].dispatchEvent(new MessageEvent("message", { data: { unexpected: true } }));
    expect(libraryTab.getCachedLibraryDecks()).toBe(previousCache);
  });

  it("still updates the current tab when BroadcastChannel is unavailable", async () => {
    vi.stubGlobal("BroadcastChannel", undefined);
    const tab = await openTab();
    cacheFavourite(tab);
    const listener = vi.fn();
    tab.subscribeToLibraryDeckSaveChanges(listener);

    tab.updateLibraryDeckSavedState(DECK_UUID, false);

    expect(tab.getCachedLibraryDecks()?.state.decks).toEqual([]);
    expect(listener).toHaveBeenCalledWith("local");
  });
});
