import { beforeEach, describe, expect, it, vi } from "vitest";
import { addLibraryCardToDeck } from "../api/library-api";
import { assignCardToDecks } from "./useCardDeckAssignment";

vi.mock("../api/library-api", () => ({
  addLibraryCardToDeck: vi.fn(),
  getLibraryDeckOptions: vi.fn(),
}));

const CARD_UUID = "413b1910-5d07-4c67-93a0-6b8946c59b15";
const FIRST_DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const SECOND_DECK_UUID = "f9b7ced5-fbea-4741-82fd-33ea144dab7c";

describe("assignCardToDecks", () => {
  beforeEach(() => {
    vi.mocked(addLibraryCardToDeck).mockReset();
  });

  it("adds a card to every selected deck and removes duplicate selections", async () => {
    vi.mocked(addLibraryCardToDeck)
      .mockResolvedValueOnce("added")
      .mockResolvedValueOnce("already-present");
    const controller = new AbortController();

    await expect(
      assignCardToDecks(
        CARD_UUID,
        [FIRST_DECK_UUID, SECOND_DECK_UUID, FIRST_DECK_UUID],
        controller.signal,
      ),
    ).resolves.toEqual([
      { deckUuid: FIRST_DECK_UUID, status: "added" },
      { deckUuid: SECOND_DECK_UUID, status: "already-present" },
    ]);

    expect(addLibraryCardToDeck).toHaveBeenCalledTimes(2);
    expect(addLibraryCardToDeck).toHaveBeenNthCalledWith(
      1,
      FIRST_DECK_UUID,
      CARD_UUID,
      controller.signal,
    );
    expect(addLibraryCardToDeck).toHaveBeenNthCalledWith(
      2,
      SECOND_DECK_UUID,
      CARD_UUID,
      controller.signal,
    );
  });

  it("waits for all deck requests and reports a partial failure", async () => {
    const error = new Error("second deck failed");
    vi.mocked(addLibraryCardToDeck).mockResolvedValueOnce("added").mockRejectedValueOnce(error);

    await expect(
      assignCardToDecks(CARD_UUID, [FIRST_DECK_UUID, SECOND_DECK_UUID]),
    ).resolves.toEqual([
      { deckUuid: FIRST_DECK_UUID, status: "added" },
      { deckUuid: SECOND_DECK_UUID, status: "failed", error },
    ]);
  });

  it("does not call the API when no decks are selected", async () => {
    await expect(assignCardToDecks(CARD_UUID, [])).resolves.toEqual([]);
    expect(addLibraryCardToDeck).not.toHaveBeenCalled();
  });
});
