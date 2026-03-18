import { apiClient } from "./client";
import type { AdmissionApplicationListResponse } from "../types";

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
