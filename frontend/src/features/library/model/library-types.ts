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
