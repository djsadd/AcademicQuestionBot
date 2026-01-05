import { apiClient } from "./client";
import type { ChatRequestPayload, ChatResponse } from "../types";

export async function sendChatMessage(payload: ChatRequestPayload): Promise<ChatResponse> {
  return apiClient.post<ChatResponse>("/chat/", JSON.stringify(payload));
}
