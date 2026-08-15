export interface CatalogDeck {
  uuid: string;
  ownerUuid: string;
  title: string;
  description: string | null;
  totalWordsCount: number;
  savesCount: number;
  isSaved: boolean;
  isPublic: boolean;
  updatedAt: string | null;
}

export interface CatalogDeckPage {
  decks: readonly CatalogDeck[];
  page: number;
  hasMore: boolean;
}

export interface CatalogDeckPreview {
  uuid: string;
  ownerUuid: string;
  title: string;
  description: string | null;
  totalWordsCount: number;
  savesCount: number;
  isPublic: boolean;
  updatedAt: string | null;
}

export interface CatalogPreviewCard {
  uuid: string;
  frontText: string;
  backText: string;
  frontLang: string;
  backLang: string;
  updatedAt: string;
}

export interface CatalogPreviewCardPage {
  cards: readonly CatalogPreviewCard[];
  nextOffset: number;
  hasMore: boolean;
}
