import { apiClient } from "./client";
import type {
  AdmissionApplicationListResponse,
  ChatAnalyticsEventListResponse,
  ChatAnalyticsSessionListResponse,
  ChatAnalyticsSummary,
  ChatAnalyticsUserListResponse,
} from "../types";

export function fetchAdmissionApplications(
  page: number,
  perPage: number,
): Promise<AdmissionApplicationListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
  });
  return apiClient.get<AdmissionApplicationListResponse>(`/admin/admission-applications?${params.toString()}`);
}

export function fetchChatAnalyticsSummary(): Promise<ChatAnalyticsSummary> {
  return apiClient.get<ChatAnalyticsSummary>("/admin/chat-analytics/summary");
}

export function fetchChatAnalyticsSessions(
  page: number,
  perPage: number,
  authMode: string,
  search: string,
): Promise<ChatAnalyticsSessionListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
    auth_mode: authMode,
    search,
  });
  return apiClient.get<ChatAnalyticsSessionListResponse>(`/admin/chat-analytics/sessions?${params.toString()}`);
}

export function fetchChatAnalyticsUsers(limit = 100): Promise<ChatAnalyticsUserListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiClient.get<ChatAnalyticsUserListResponse>(`/admin/chat-analytics/users?${params.toString()}`);
}

export function fetchChatAnalyticsSessionEvents(sessionKey: string): Promise<ChatAnalyticsEventListResponse> {
  return apiClient.get<ChatAnalyticsEventListResponse>(`/admin/chat-analytics/sessions/${encodeURIComponent(sessionKey)}`);
}
