import { apiClient, API_BASE_URL, authStorage } from "./client";
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

export async function streamChatMessage(
  payload: ChatRequestPayload,
  handlers: StreamHandlers = {},
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const refreshToken = authStorage.getRefreshToken();
  const tryRefresh = async () => {
    if (!refreshToken) return false;
    const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
      signal,
    });
    if (!refreshResponse.ok) {
      authStorage.clearTokens();
      return false;
    }
    const data = (await refreshResponse.json()) as {
      access_token: string;
      refresh_token: string;
    };
    authStorage.setTokens(data.access_token, data.refresh_token);
    return true;
  };

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const doFetch = () =>
    fetch(`${API_BASE_URL}/chat/stream`, {
      method: "POST",
      headers: {
        ...headers,
        ...(authStorage.getAccessToken()
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
