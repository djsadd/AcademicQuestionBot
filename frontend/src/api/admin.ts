import { apiClient } from "./client";
import type {
  AdminUserListResponse,
  AdminUserRoleUpdateResponse,
  AdmissionApplicationListResponse,
  AdmissionInfoPayload,
  AdmissionInfoResponse,
  AdmissionProgramsListResponse,
  AgentOverviewResponse,
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

export function fetchAdmissionInfo(): Promise<AdmissionInfoResponse> {
  return apiClient.get<AdmissionInfoResponse>("/admin/admission-info");
}

export function fetchAdmissionPrograms(
  page: number,
  perPage: number,
  level: string,
  search: string,
): Promise<AdmissionProgramsListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
    level,
    search,
  });
  return apiClient.get<AdmissionProgramsListResponse>(`/admin/admission-programs?${params.toString()}`);
}

export function updateAdmissionInfo(payload: AdmissionInfoPayload): Promise<AdmissionInfoResponse> {
  return apiClient.put<AdmissionInfoResponse>("/admin/admission-info", JSON.stringify(payload));
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

export function fetchAdminUsers(limit = 100): Promise<AdminUserListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiClient.get<AdminUserListResponse>(`/admin/users?${params.toString()}`);
}

export function updateAdminUserRole(
  telegramId: number,
  role: string | null,
): Promise<AdminUserRoleUpdateResponse> {
  return apiClient.put<AdminUserRoleUpdateResponse>(
    `/admin/users/${telegramId}/role`,
    JSON.stringify({ role }),
  );
}

export function fetchChatAnalyticsSessionEvents(sessionKey: string): Promise<ChatAnalyticsEventListResponse> {
  return apiClient.get<ChatAnalyticsEventListResponse>(`/admin/chat-analytics/sessions/${encodeURIComponent(sessionKey)}`);
}

export function fetchAgentsOverview(days = 30): Promise<AgentOverviewResponse> {
  const params = new URLSearchParams({ days: String(days) });
  return apiClient.get<AgentOverviewResponse>(`/admin/agents/overview?${params.toString()}`);
}
