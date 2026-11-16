export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api";

const ACCESS_TOKEN_KEY = "aqb_access_token";
const REFRESH_TOKEN_KEY = "aqb_refresh_token";
const AUTH_STORAGE_EVENT = "aqb-auth-changed";

function emitAuthStorageChange() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(AUTH_STORAGE_EVENT));
}

export const authStorage = {
  getAccessToken: () => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefreshToken: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  setTokens: (accessToken: string, refreshToken: string) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    emitAuthStorageChange();
  },
  clearTokens: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    emitAuthStorageChange();
  },
};

export { AUTH_STORAGE_EVENT };

let refreshRequest: Promise<void> | null = null;

const STATUS_MESSAGES: Record<number, string> = {
  401: "Сессия истекла. Войдите снова.",
  403: "Недостаточно прав для этого действия.",
  404: "Не найдено.",
  413: "Файл слишком большой.",
  415: "Неподдерживаемый формат файла.",
  429: "Слишком много запросов. Подождите немного и попробуйте снова.",
  500: "Ошибка сервера. Попробуйте позже.",
  502: "Сервис временно недоступен. Попробуйте позже.",
  503: "Сервис временно недоступен. Попробуйте позже.",
  504: "Сервер не ответил вовремя. Попробуйте ещё раз.",
};

/** Turn an error response into a human-readable message (FastAPI `detail` aware). */
export async function describeHttpError(response: Response): Promise<string> {
  let text = "";
  try {
    text = await response.text();
  } catch {
    // ignore body read errors
  }
  try {
    const data = JSON.parse(text) as { detail?: unknown };
    if (typeof data.detail === "string" && data.detail.trim()) return data.detail;
    if (Array.isArray(data.detail) && data.detail.length) {
      const first = data.detail[0] as { msg?: string };
      if (first?.msg) return first.msg.replace(/^Value error, /, "");
    }
  } catch {
    // not JSON
  }
  return STATUS_MESSAGES[response.status] ?? (text.length < 200 && text ? text : `Ошибка запроса (${response.status})`);
}

export function hasStoredSession(): boolean {
  return Boolean(authStorage.getAccessToken() || authStorage.getRefreshToken());
}

export async function refreshTokens(): Promise<void> {
  const refreshToken = authStorage.getRefreshToken();
  if (!refreshToken) {
    throw new Error("Refresh token missing.");
  }

  if (!refreshRequest) {
    refreshRequest = (async () => {
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
    })().finally(() => {
      refreshRequest = null;
    });
  }

  await refreshRequest;
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
    throw new Error(await describeHttpError(response));
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
  put: <T>(url: string, body?: BodyInit | null) =>
    request<T>(url, {
      method: "PUT",
      body,
    }),
  patch: <T>(url: string, body?: BodyInit | null) =>
    request<T>(url, {
      method: "PATCH",
      body,
    }),
  delete: <T>(url: string) =>
    request<T>(url, {
      method: "DELETE",
    }),
};
