import { apiClient, API_BASE_URL, authStorage, refreshTokens } from "./client";
import type { ChatHistoryResponse, ChatRequestPayload, ChatResponse } from "../types";

export async function sendChatMessage(payload: ChatRequestPayload): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>("/chat/", JSON.stringify(payload));
}

export async function sendPublicAdmissionMessage(
  payload: ChatRequestPayload,
): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>("/chat/public/admission", JSON.stringify(payload));
}

export async function getChatHistory(): Promise<ChatHistoryResponse> {
  return apiClient.get<ChatHistoryResponse>("/chat/history");
}

type StreamHandlers = {
  onDelta?: (delta: string) => void;
  onError?: (error: string) => void;
};

async function streamChatRequest(
  endpoint: string,
  payload: ChatRequestPayload,
  handlers: StreamHandlers = {},
  signal?: AbortSignal,
  requireAuth = true,
): Promise<ChatResponse> {
  const tryRefresh = async () => {
    if (!authStorage.getRefreshToken() || !requireAuth) return false;
    try {
      await refreshTokens();
      return true;
    } catch {
      return false;
    }
  };

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const doFetch = () =>
    fetch(`${API_BASE_URL}${endpoint}`, {
      method: "POST",
      headers: {
        ...headers,
        ...(requireAuth && authStorage.getAccessToken()
          ? { Authorization: `Bearer ${authStorage.getAccessToken()}` }
          : {}),
      },
      body: JSON.stringify(payload),
      signal,
    });

  let response = await doFetch();
  if (response.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      response = await doFetch();
    }
  }

  if (!response.ok || !response.body) {
    const detail = await response.text();
    throw new Error(detail || `Stream failed with status ${response.status}`);
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let buffer = "";
  let donePayload: ChatResponse | null = null;

  const flushEvent = (rawEvent: string) => {
    const lines = rawEvent.split("\n").map((line) => line.trimEnd());
    let eventType = "message";
    const dataLines: string[] = [];
    for (const line of lines) {
      if (!line) continue;
      if (line.startsWith("event:")) {
        eventType = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trimStart());
      }
    }
    const dataText = dataLines.join("\n").trim();
    if (!dataText) return;

    try {
      const data = JSON.parse(dataText) as any;
      if (eventType === "delta" && typeof data.delta === "string") {
        handlers.onDelta?.(data.delta);
      } else if (eventType === "done" && data.result) {
        donePayload = { result: data.result };
      } else if (eventType === "error" && typeof data.error === "string") {
        handlers.onError?.(data.error);
        throw new Error(data.error);
      }
    } catch (err) {
      if (err instanceof Error) throw err;
    }
  };

  while (true) {
    const chunk = await reader.read();
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      flushEvent(part);
    }
    if (donePayload) break;
  }

  if (!donePayload) {
    throw new Error("Stream ended without a final response.");
  }
  return donePayload;
}

export async function streamChatMessage(
  payload: ChatRequestPayload,
  handlers: StreamHandlers = {},
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return streamChatRequest("/chat/stream", payload, handlers, signal, true);
}

export async function streamPublicAdmissionMessage(
  payload: ChatRequestPayload,
  handlers: StreamHandlers = {},
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return streamChatRequest("/chat/public/admission/stream", payload, handlers, signal, false);
}
