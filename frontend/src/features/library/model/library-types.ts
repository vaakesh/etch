export interface LibraryPreviewCard {
  uuid: string;
  frontText: string;
  backText: string;
}

export interface LibraryDeck {
  uuid: string;
  title: string;
  description: string | null;
  totalWordsCount: number;
  accuracy: number;
  isFavourite: boolean;
  updatedAt: string | null;
  cards: readonly LibraryPreviewCard[];
}

export interface LibraryDeckPage {
  decks: readonly LibraryDeck[];
  nextCursor: string | null;
  hasMore: boolean;
}

export interface FavouriteLibraryDeck {
  uuid: string;
  ownerUuid: string;
  title: string;
  description?: string | null;
  totalWordsCount: number;
  accuracy: number;
  updatedAt?: string | null;
  isFavourite: boolean;
  isFollowing: boolean;
  cards: readonly LibraryPreviewCard[];
}

export interface FavouriteLibraryDeckPage {
  decks: readonly FavouriteLibraryDeck[];
  nextCursor: string | null;
  hasMore: boolean;
}

export type LibraryDeckItem = LibraryDeck | FavouriteLibraryDeck;

export interface LibraryFavouriteResult {
  isFavourite: boolean;
}
