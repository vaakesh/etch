import { beforeEach, describe, expect, it, vi } from "vitest";

const apiFetchMock = vi.hoisted(() => vi.fn());
vi.mock("../../../api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../api")>();
  return { ...original, apiFetch: apiFetchMock };
});

import {
  getArchiveCards,
  getArchivedDeck,
  getArchiveOffers,
  preserveArchivedDeck,
} from "./archive-api";

const ARCHIVE_UUID = "0199c27d-9a31-7e11-8f08-b193932384e5";

describe("archive API", () => {
  beforeEach(() => apiFetchMock.mockReset());

  it("uses the archive endpoints and card pagination", async () => {
    const signal = new AbortController().signal;
    apiFetchMock.mockResolvedValueOnce([]);
    await getArchiveOffers(signal);
    expect(apiFetchMock).toHaveBeenLastCalledWith("/decks/archives", { signal });

    apiFetchMock.mockResolvedValueOnce({
      uuid: ARCHIVE_UUID,
      title: "Travel",
      description: null,
      words_count: 0,
      archived_at: "2026-09-28T12:00:00Z",
      expires_at: "2026-10-28T12:00:00Z",
      archive_reason: "deleted",
      source_deck_uuid_snapshot: null,
      preserved_deck_uuid: null,
    });
    await getArchivedDeck(ARCHIVE_UUID, signal);
    expect(apiFetchMock).toHaveBeenLastCalledWith(`/decks/archives/${ARCHIVE_UUID}`, { signal });

    apiFetchMock.mockResolvedValueOnce([]);
    await getArchiveCards(ARCHIVE_UUID, 50, signal);
    expect(apiFetchMock).toHaveBeenLastCalledWith(`/decks/archives/${ARCHIVE_UUID}/cards`, {
      query: { offset: 50, limit: 50 },
      signal,
    });
  });

  it("preserves an archive with the backend route and parses the copy status", async () => {
    const copyUuid = "0199c27d-9a31-7e12-8f08-b193932384e5";
    apiFetchMock.mockResolvedValueOnce({
      uuid: copyUuid,
      already_preserved: false,
      copy_deleted: false,
    });

    await expect(preserveArchivedDeck(ARCHIVE_UUID)).resolves.toEqual({
      uuid: copyUuid,
      alreadyPreserved: false,
      copyDeleted: false,
    });
    expect(apiFetchMock).toHaveBeenLastCalledWith(`/decks/${ARCHIVE_UUID}/preserve`, {
      method: "POST",
      signal: undefined,
    });

    apiFetchMock.mockResolvedValueOnce({
      uuid: copyUuid,
      already_preserved: true,
      copy_deleted: true,
    });
    await expect(preserveArchivedDeck(ARCHIVE_UUID)).resolves.toMatchObject({ copyDeleted: true });
  });
});
