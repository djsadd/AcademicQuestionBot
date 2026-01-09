import { apiClient } from "./client";
import type { ChatHistoryResponse, ChatRequestPayload, ChatResponse } from "../types";

export async function sendChatMessage(payload: ChatRequestPayload): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>("/chat/", JSON.stringify(payload));
}

export async function getChatHistory(): Promise<ChatHistoryResponse> {
  return apiClient.get<ChatHistoryResponse>("/chat/history");
}
