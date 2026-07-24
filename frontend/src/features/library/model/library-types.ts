export interface LibraryPreviewCard {
  uuid: string;
  frontText: string;
  backText: string;
}

export interface EditableLibraryCard {
  uuid: string;
  frontText: string;
  backText: string;
  sourceLang: string;
  targetLang: string;
  updatedAt: string;
}

export interface LibraryCard extends EditableLibraryCard {
  ownerUuid: string;
}

export interface LibraryCardPage {
  cards: readonly LibraryCard[];
  nextCursor: string | null;
  hasMore: boolean;
}

export interface DeckCardPage {
  cards: readonly EditableLibraryCard[];
  nextOffset: number;
  hasMore: boolean;
}

export interface UpdateLibraryCardInput {
  frontText: string;
  backText: string;
  sourceLang: string;
  targetLang: string;
}

export type CreateLibraryCardInput = UpdateLibraryCardInput;

export interface CreatedLibraryCard extends CreateLibraryCardInput {
  uuid: string;
}

export interface UpdatedLibraryCard extends UpdateLibraryCardInput {
  uuid: string;
  updatedAt: string;
}

export interface EditableLibraryDeck {
  uuid: string;
  title: string;
  description: string | null;
  totalWordsCount: number;
  isPublic: boolean;
  updatedAt: string | null;
}

export interface UpdateLibraryDeckInput {
  title: string;
  description: string | null;
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

export interface LibraryDeckOption {
  uuid: string;
  title: string;
  totalWordsCount: number;
}

export type LibraryCardDeckAddStatus = "added" | "already-present";

export interface CreateLibraryDeckInput {
  title: string;
  description: string | null;
  isPublic: boolean;
}

export interface CreatedLibraryDeck {
  uuid: string;
  title: string;
  description: string | null;
  totalWordsCount: number;
  isPublic: boolean;
  updatedAt: string | null;
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
