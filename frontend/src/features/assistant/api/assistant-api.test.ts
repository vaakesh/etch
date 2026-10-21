import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch } from "../../../api";
import { askAssistant } from "./assistant-api";

vi.mock("../../../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../api")>();
  return { ...actual, apiFetch: vi.fn() };
});

describe("askAssistant", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("posts the trimmed question and returns only answer text", async () => {
    const controller = new AbortController();
    vi.mocked(apiFetch).mockResolvedValue({
      text: " Откройте раздел импорта. ",
      sources: [{ text: "private" }],
    });

    await expect(
      askAssistant("  Как импортировать карточки?  ", controller.signal),
    ).resolves.toEqual({ text: "Откройте раздел импорта." });

    expect(apiFetch).toHaveBeenCalledOnce();
    expect(apiFetch).toHaveBeenCalledWith("/ask", {
      method: "POST",
      body: { message: "Как импортировать карточки?" },
      signal: controller.signal,
    });
  });

  it.each(["", " \n ", "я".repeat(201)])(
    "rejects invalid questions before making a request: %j",
    async (message) => {
      await expect(askAssistant(message)).rejects.toMatchObject({ code: "INVALID_ASK_MESSAGE" });

      expect(apiFetch).not.toHaveBeenCalled();
    },
  );

  it("accepts 200 Unicode code points", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ text: "Ответ" });

    await expect(askAssistant("😀".repeat(200))).resolves.toEqual({ text: "Ответ" });
  });

  it.each([null, {}, { text: "" }, { text: "  " }, { text: 3 }])(
    "rejects malformed response %j",
    async (payload) => {
      vi.mocked(apiFetch).mockResolvedValue(payload);

      await expect(askAssistant("Как начать практику?")).rejects.toMatchObject({
        code: "INVALID_ASK_RESPONSE",
      });
    },
  );

  it("preserves API errors without retrying the question", async () => {
    const error = new ApiError({
      status: 429,
      code: "RATE_LIMIT_EXCEEDED",
      message: "Limit reached",
    });
    vi.mocked(apiFetch).mockRejectedValue(error);

    await expect(askAssistant("Как начать практику?")).rejects.toBe(error);

    expect(apiFetch).toHaveBeenCalledOnce();
  });
});
