export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  get: <T>(url: string) => request<T>(url),
  post: <T>(url: string, body?: BodyInit | null) =>
    request<T>(url, {
      method: "POST",
      body,
    }),
  delete: <T>(url: string) =>
    request<T>(url, {
      method: "DELETE",
    }),
};
