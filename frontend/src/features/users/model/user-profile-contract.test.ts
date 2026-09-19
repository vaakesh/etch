import { describe, expect, it } from "vitest";
import { parseUserProfile, parseUserProfileDeckPage } from "./user-profile-contract";

const PROFILE = {
  uuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
  username: "deck-owner",
  created_at: "2024-03-12T14:35:00Z",
  deck_count: 7,
  total_saves_count: 42,
};

const DECK = {
  uuid: "714d882d-726e-4dcb-9303-a8bf4638429c",
  owner_uuid: PROFILE.uuid,
  owner_username: PROFILE.username,
  title: "Daily Words",
  description: "Core vocabulary",
  words_count: 48,
  is_public: true,
  saves_count: 12,
  updated_at: "2026-07-17T10:30:00Z",
};

describe("user profile contract", () => {
  it("maps UserProfileResponse and CursorPage[DeckResponse]", () => {
    expect(parseUserProfile(PROFILE)).toEqual({
      uuid: PROFILE.uuid,
      username: "deck-owner",
      createdAt: "2024-03-12T14:35:00Z",
      deckCount: 7,
      totalSavesCount: 42,
    });

    expect(
      parseUserProfileDeckPage({
        items: [DECK],
        next_cursor: "next-page",
        has_more: true,
      }),
    ).toEqual({
      decks: [
        {
          uuid: DECK.uuid,
          ownerUuid: PROFILE.uuid,
          ownerUsername: "deck-owner",
          title: "Daily Words",
          description: "Core vocabulary",
          totalWordsCount: 48,
          savesCount: 12,
          isSaved: false,
          isPublic: true,
          updatedAt: "2026-07-17T10:30:00Z",
        },
      ],
      nextCursor: "next-page",
      hasMore: true,
    });
  });

  it("rejects inconsistent cursors and invalid counters", () => {
    expect(() =>
      parseUserProfileDeckPage({ items: [], next_cursor: null, has_more: true }),
    ).toThrowError(expect.objectContaining({ code: "INVALID_USER_PROFILE_RESPONSE" }));
    expect(() => parseUserProfile({ ...PROFILE, total_saves_count: -1 })).toThrowError(
      expect.objectContaining({ code: "INVALID_USER_PROFILE_RESPONSE" }),
    );
  });
});
