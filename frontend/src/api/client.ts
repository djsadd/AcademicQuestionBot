export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

const ACCESS_TOKEN_KEY = "aqb_access_token";
const REFRESH_TOKEN_KEY = "aqb_refresh_token";

export const authStorage = {
  getAccessToken: () => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefreshToken: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  setTokens: (accessToken: string, refreshToken: string) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },
  clearTokens: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

async function refreshTokens(): Promise<void> {
  const refreshToken = authStorage.getRefreshToken();
  if (!refreshToken) {
    throw new Error("Refresh token missing.");
  }
  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!response.ok) {
    authStorage.clearTokens();
    const detail = await response.text();
    throw new Error(detail || `Refresh failed with status ${response.status}`);
  }
  const data = (await response.json()) as {
    access_token: string;
    refresh_token: string;
  };
  authStorage.setTokens(data.access_token, data.refresh_token);
}

async function request<T>(url: string, init?: RequestInit, retried?: boolean): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const accessToken = authStorage.getAccessToken();
  if (accessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...init,
    headers,
  });

  if (response.status === 401 && !retried && authStorage.getRefreshToken()) {
    await refreshTokens();
    return request<T>(url, init, true);
  }

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
