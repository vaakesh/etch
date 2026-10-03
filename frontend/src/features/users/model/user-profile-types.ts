export interface UserProfile {
  uuid: string;
  username: string;
  createdAt: string;
  deckCount: number;
  totalSavesCount: number;
}

export interface UserProfileDeck {
  uuid: string;
  ownerUuid: string;
  ownerUsername: string;
  title: string;
  description: string | null;
  totalWordsCount: number;
  savesCount: number;
  isSaved: boolean;
  isPublic: boolean;
  updatedAt: string | null;
}

export interface UserProfileDeckPage {
  decks: readonly UserProfileDeck[];
  nextCursor: string | null;
  hasMore: boolean;
}
