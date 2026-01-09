import { apiClient } from "./client";

export interface PlatonusSessionStatus {
  token_present: boolean;
  cookie_present: boolean;
  sid_present: boolean;
  user_agent_present: boolean;
  last_login: number | null;
  age_seconds: number | null;
  refresh_seconds: number;
}

export function fetchPlatonusSession() {
  return apiClient.get<PlatonusSessionStatus>("/admin/platonus/session");
}

export function fetchStudentAcademicCalendar(personId: string, lang = "ru") {
  return apiClient.get<unknown>(
    `/admin/platonus/student-academic-calendar/${encodeURIComponent(
      personId
    )}?lang=${encodeURIComponent(lang)}`
  );
}
