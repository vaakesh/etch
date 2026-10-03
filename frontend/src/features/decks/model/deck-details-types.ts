export interface DeckDetails {
  uuid: string;
  ownerUuid: string;
  ownerUsername: string;
  title: string;
  description: string | null;
  totalWordsCount: number;
  savesCount: number;
  isPublic: boolean;
  updatedAt: string | null;
}

export interface DeckDetailsCard {
  uuid: string;
  frontText: string;
  backText: string;
  frontLang: string;
  backLang: string;
  updatedAt: string;
}

export interface DeckDetailsCardBatch {
  cards: readonly DeckDetailsCard[];
  offset: number;
  hasMore: boolean;
}

export interface UpdateDeckDetailsCardInput {
  frontText: string;
  backText: string;
  frontLang: string;
  backLang: string;
}
