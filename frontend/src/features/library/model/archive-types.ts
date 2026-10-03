export interface ArchiveOffer {
  uuid: string;
  title: string;
  expiresAt: string;
  preservedDeckUuid: string | null;
}

export interface ArchivedDeck {
  uuid: string;
  title: string;
  description: string | null;
  wordsCount: number;
  archivedAt: string;
  expiresAt: string;
  archiveReason: "deleted" | "owner_deleted" | "made_private";
  sourceDeckUuidSnapshot: string | null;
  preservedDeckUuid: string | null;
}

export interface ArchiveCard {
  uuid: string;
  frontText: string;
  backText: string;
  frontLang: string;
  backLang: string;
  updatedAt: string;
}

export interface PreservedArchive {
  uuid: string;
  alreadyPreserved: boolean;
  copyDeleted: boolean;
}
