import { useEffect, useRef, useState } from "react";
import { isApiError } from "../../../api";
import { askAssistant } from "../api/assistant-api";

interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
}

type ChatError = "limit" | "unavailable" | "timeout" | "invalid" | "network" | "access";

function getChatError(error: unknown): ChatError {
  if (!isApiError(error)) return "unavailable";
  if (error.status === 429) return "limit";
  if (error.status === 401 || error.status === 403) return "access";
  if (error.code === "RAG_TIMEOUT" || error.status === 504) return "timeout";
  if (
    error.code === "RAG_BAD_RESPONSE" ||
    error.code === "INVALID_ASK_RESPONSE" ||
    error.status === 502
  )
    return "invalid";
  if (error.code === "NETWORK_ERROR") return "network";
  return "unavailable";
}

export function useAssistantChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<ChatError | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const sequenceRef = useRef(0);

  useEffect(() => () => requestRef.current?.abort(), []);

  async function sendMessage() {
    const question = draft.trim();
    if (!question || requestRef.current !== null) return;

    const controller = new AbortController();
    requestRef.current = controller;
    const id = sequenceRef.current++;
    setMessages((current) => [...current, { id, role: "user", text: question }]);
    setDraft("");
    setError(null);
    setIsPending(true);

    try {
      const answer = await askAssistant(question, controller.signal);
      if (controller.signal.aborted) return;
      const answerId = sequenceRef.current++;
      setMessages((current) => [
        ...current,
        { id: answerId, role: "assistant", text: answer.text },
      ]);
    } catch (cause) {
      if (controller.signal.aborted) return;
      setError(getChatError(cause));
      setDraft(question);
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        if (!controller.signal.aborted) setIsPending(false);
      }
    }
  }

  return { messages, draft, setDraft, isPending, error, sendMessage };
}
