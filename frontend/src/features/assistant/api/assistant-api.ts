import { ApiError, apiFetch } from "../../../api";

export const ASK_MESSAGE_MAX_LENGTH = 200;

export interface AskAnswer {
  text: string;
}

export async function askAssistant(message: string, signal?: AbortSignal): Promise<AskAnswer> {
  const normalized = message.trim();
  if (!normalized || Array.from(normalized).length > ASK_MESSAGE_MAX_LENGTH) {
    throw new ApiError({
      status: 0,
      code: "INVALID_ASK_MESSAGE",
      message: "The question must contain between 1 and 200 characters.",
    });
  }

  const payload = await apiFetch<unknown>("/ask", {
    method: "POST",
    body: { message: normalized },
    signal,
  });

  if (
    typeof payload !== "object" ||
    payload === null ||
    !("text" in payload) ||
    typeof payload.text !== "string" ||
    !payload.text.trim()
  ) {
    throw new ApiError({
      status: 0,
      code: "INVALID_ASK_RESPONSE",
      message: "The assistant returned an unexpected response.",
    });
  }

  return { text: payload.text.trim() };
}
