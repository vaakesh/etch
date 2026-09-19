export interface LibraryPreviewCard {
  uuid: string;
  frontText: string;
  backText: string;
  frontLang: string;
  backLang: string;
  updatedAt: string;
}

export interface EditableLibraryCard {
  uuid: string;
  frontText: string;
  backText: string;
  frontLang: string;
  backLang: string;
}

export interface LibraryCard extends EditableLibraryCard {
  updatedAt: string;
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
  frontLang: string;
  backLang: string;
}

export type CreateLibraryCardInput = UpdateLibraryCardInput;

export interface CreatedLibraryCard extends CreateLibraryCardInput {
  uuid: string;
}

export interface UpdatedLibraryCard extends UpdateLibraryCardInput {
  uuid: string;
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
  isPublic: boolean;
}

export interface LibraryDeck {
  uuid: string;
  ownerUuid: string;
  ownerUsername: string;
  title: string;
  description: string | null;
  totalWordsCount: number;
  savesCount: number;
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

export interface LibraryDeckOptionPage {
  decks: readonly LibraryDeckOption[];
  nextCursor: string | null;
  hasMore: boolean;
}

export type LibraryCardDeckAddStatus = "added" | "already-present";

export interface CreateLibraryDeckInput {
  title: string;
  description: string | null;
  isPublic: boolean;
}

export interface CreatedLibraryDeck {
  uuid: string;
  ownerUsername: string;
  title: string;
  description: string | null;
  totalWordsCount: number;
  savesCount: number;
  isPublic: boolean;
  updatedAt: string | null;
}

export interface LibraryDeckPage {
  decks: readonly LibraryDeck[];
  nextCursor: string | null;
  hasMore: boolean;
}

export type LibraryDeckItem = LibraryDeck;

export interface LibraryFavouriteResult {
  isFavourite: boolean;
}

export interface ImportLibraryCardInput {
  frontText: string;
  backText: string;
  frontLang: string;
  backLang: string;
}

export interface ImportLibraryCardsInput {
  cards: readonly ImportLibraryCardInput[];
}

export interface ImportedLibraryCard {
  uuid: string;
  position: number;
}

export interface ImportLibraryCardsResult {
  importedCount: number;
  cards: readonly ImportedLibraryCard[];
}
