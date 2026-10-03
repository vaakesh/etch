import { describe, expect, it } from "vitest";
import {
  parseArchiveCards,
  parseArchivedDeck,
  parseArchiveOffers,
  parsePreservedArchive,
} from "./archive-contract";

const ARCHIVE_UUID = "0199c27d-9a31-7e11-8f08-b193932384e5";
const COPY_UUID = "0199c27d-9a31-7e12-8f08-b193932384e5";

describe("archive response contract", () => {
  it("parses archive offers, details and cards with nullable preservation fields", () => {
    expect(
      parseArchiveOffers([
        {
          uuid: ARCHIVE_UUID,
          title: "Travel",
          expires_at: "2026-10-28T12:00:00Z",
          preserved_deck_uuid: null,
        },
      ]),
    ).toEqual([
      {
        uuid: ARCHIVE_UUID,
        title: "Travel",
        expiresAt: "2026-10-28T12:00:00Z",
        preservedDeckUuid: null,
      },
    ]);

    expect(
      parseArchivedDeck({
        uuid: ARCHIVE_UUID,
        title: "Travel",
        description: null,
        words_count: 1,
        archived_at: "2026-09-28T12:00:00Z",
        expires_at: "2026-10-28T12:00:00Z",
        archive_reason: "made_private",
        source_deck_uuid_snapshot: COPY_UUID,
        preserved_deck_uuid: null,
      }).archiveReason,
    ).toBe("made_private");

    expect(
      parseArchiveCards(
        [
          {
            uuid: COPY_UUID,
            front_text: "hello",
            back_text: "привет",
            front_lang: "en",
            back_lang: "ru",
            updated_at: "2026-09-28T12:00:00Z",
          },
        ],
        50,
      )[0]?.backText,
    ).toBe("привет");
  });

  it("rejects incomplete or oversized responses", () => {
    expect(() => parseArchiveOffers([{ uuid: ARCHIVE_UUID, title: "Missing fields" }])).toThrow();
    expect(() => parseArchivedDeck({ uuid: ARCHIVE_UUID })).toThrow();
    expect(() => parseArchiveCards([{}, {}], 1)).toThrow();
    expect(() =>
      parsePreservedArchive({ uuid: ARCHIVE_UUID, already_preserved: false, copy_deleted: true }),
    ).toThrow();
  });
});
