import { ApiError, apiFetch } from "../../../api";
import { parseUserProfile, parseUserProfileDeckPage } from "../model/user-profile-contract";
import type { UserProfile, UserProfileDeckPage } from "../model/user-profile-types";

export const USER_PROFILE_DECK_PAGE_SIZE = 30;

export async function getUserProfile(username: string, signal?: AbortSignal): Promise<UserProfile> {
  const payload = await apiFetch<unknown>(`/users/profile/${encodeURIComponent(username)}`, {
    signal,
  });
  return parseUserProfile(payload);
}

export async function getUserProfileDeckPage(
  userUuid: string,
  cursor: string | null,
  signal?: AbortSignal,
): Promise<UserProfileDeckPage> {
  const payload = await apiFetch<unknown>(`/users/${encodeURIComponent(userUuid)}/decks`, {
    query: {
      limit: USER_PROFILE_DECK_PAGE_SIZE,
      ...(cursor === null ? {} : { cursor }),
    },
    signal,
  });
  const page = parseUserProfileDeckPage(payload);

  if (page.decks.some((deck) => deck.ownerUuid.toLowerCase() !== userUuid.toLowerCase())) {
    throw new ApiError({
      status: 0,
      code: "INVALID_USER_PROFILE_RESPONSE",
      message: "The backend returned a deck owned by a different user.",
    });
  }

  return page;
}
