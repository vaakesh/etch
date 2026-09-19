import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch } from "../../../api";
import { DECK_DETAILS_CARD_BATCH_SIZE } from "../model/deck-details-pagination";
import {
  deleteDeckDetailsCard,
  deleteDeckFromDetails,
  getDeckDetailsCardBatch,
  getDeckDetailsInitialData,
  updateDeckDetailsCard,
} from "./deck-details-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

const DECK_UUID = "714d882d-726e-4dcb-9303-a8bf4638429c";
const DECK_RESPONSE = {
  uuid: DECK_UUID,
  owner_uuid: "d2f61c35-11d0-489e-837d-3845418ba39e",
  owner_username: "deck-owner",
  title: "Daily Words",
  description: "Core vocabulary",
  words_count: 750,
  saves_count: 12,
  is_public: true,
  updated_at: "2026-09-10T10:00:00Z",
};
const CARD_UUID = "413b1910-5d07-4c67-93a0-6b8946c59b15";

describe("deck details API", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("loads card batches in groups of 300", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValue([]);

    await expect(getDeckDetailsCardBatch(DECK_UUID, 600, controller.signal)).resolves.toEqual({
      cards: [],
      offset: 600,
      hasMore: false,
    });

    expect(DECK_DETAILS_CARD_BATCH_SIZE).toBe(300);
    expect(apiFetch).toHaveBeenCalledWith(`/decks/${DECK_UUID}/cards`, {
      query: { offset: 600, limit: 300 },
      signal: controller.signal,
    });
  });

  it("loads the deck and its first six card pages through two requests", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValueOnce(DECK_RESPONSE).mockResolvedValueOnce([]);

    await expect(getDeckDetailsInitialData(DECK_UUID, controller.signal)).resolves.toMatchObject({
      deck: {
        uuid: DECK_UUID,
        ownerUuid: DECK_RESPONSE.owner_uuid,
        ownerUsername: DECK_RESPONSE.owner_username,
      },
      cardBatch: { cards: [], offset: 0 },
    });

    expect(apiFetch).toHaveBeenCalledTimes(2);
    expect(apiFetch).toHaveBeenNthCalledWith(1, `/decks/${DECK_UUID}`, {
      signal: controller.signal,
    });
    expect(apiFetch).toHaveBeenNthCalledWith(2, `/decks/${DECK_UUID}/cards`, {
      query: { offset: 0, limit: 300 },
      signal: controller.signal,
    });
  });

  it("updates a card through the existing card endpoint", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValue({
      uuid: CARD_UUID,
      front_text: "путешествие",
      back_text: "viaje",
      front_lang: "ru",
      back_lang: "es",
      updated_at: "2026-09-10T11:00:00Z",
    });

    await expect(
      updateDeckDetailsCard(
        CARD_UUID,
        {
          frontText: "путешествие",
          backText: "viaje",
          frontLang: "ru",
          backLang: "es",
        },
        controller.signal,
      ),
    ).resolves.toMatchObject({ uuid: CARD_UUID, backText: "viaje" });

    expect(apiFetch).toHaveBeenCalledWith(`/cards/${CARD_UUID}`, {
      method: "PATCH",
      body: {
        front_text: "путешествие",
        back_text: "viaje",
        front_lang: "ru",
        back_lang: "es",
      },
      signal: controller.signal,
    });
  });

  it("deletes cards and decks through their existing endpoints", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValue(undefined);

    await deleteDeckDetailsCard(CARD_UUID, controller.signal);
    await deleteDeckFromDetails(DECK_UUID, controller.signal);

    expect(apiFetch).toHaveBeenNthCalledWith(1, `/cards/${CARD_UUID}`, {
      method: "DELETE",
      signal: controller.signal,
    });
    expect(apiFetch).toHaveBeenNthCalledWith(2, `/decks/${DECK_UUID}`, {
      method: "DELETE",
      signal: controller.signal,
    });
  });
});
