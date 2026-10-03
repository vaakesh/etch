import { afterEach, describe, expect, it } from "vitest";
import { clearSessionCache, startSessionCache } from "../../../auth/model/session-cache";
import { updateLibraryDeckSavedState } from "../../library/model/library-decks-cache";
import {
  clearCachedCatalogDeckPage,
  getCachedCatalogDeckPage,
  setCachedCatalogDeckPage,
} from "./catalog-decks-cache";
import type { CatalogDeckPage } from "./catalog-types";

const USER_UUID = "d2f61c35-11d0-489e-837d-3845418ba39e";
const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const catalogPage: CatalogDeckPage = {
  page: 2,
  hasMore: true,
  decks: [
    {
      uuid: DECK_UUID,
      ownerUuid: USER_UUID,
      ownerUsername: "deck-owner",
      title: "Daily Words",
      description: null,
      totalWordsCount: 48,
      savesCount: 12,
      isSaved: false,
      isPublic: true,
      updatedAt: null,
    },
  ],
};

afterEach(() => clearSessionCache());

describe("catalog deck page cache", () => {
  it("restores only the same search and page in the active session", () => {
    const scope = startSessionCache(USER_UUID);
    setCachedCatalogDeckPage(scope, "travel", catalogPage);

    expect(getCachedCatalogDeckPage(scope, "travel", 2)).toBe(catalogPage);
    expect(getCachedCatalogDeckPage(scope, "travel", 1)).toBeNull();
    expect(getCachedCatalogDeckPage(scope, "other", 2)).toBeNull();

    const nextScope = startSessionCache(USER_UUID);
    expect(getCachedCatalogDeckPage(scope, "travel", 2)).toBeNull();
    expect(getCachedCatalogDeckPage(nextScope, "travel", 2)).toBeNull();
  });

  it("invalidates the result after a save change", () => {
    const scope = startSessionCache(USER_UUID);
    setCachedCatalogDeckPage(scope, "", catalogPage);

    updateLibraryDeckSavedState(DECK_UUID, true);

    expect(getCachedCatalogDeckPage(scope, "", 2)).toBeNull();
  });

  it("allows an explicit refresh to discard a result", () => {
    const scope = startSessionCache(USER_UUID);
    setCachedCatalogDeckPage(scope, "", catalogPage);

    clearCachedCatalogDeckPage(scope);

    expect(getCachedCatalogDeckPage(scope, "", 2)).toBeNull();
  });
});
