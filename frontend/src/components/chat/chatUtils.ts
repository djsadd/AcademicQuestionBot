import type { ChatHistoryEntry, ChatHistorySession, ChatResult, ChatStageEvent } from "../../types";

export type ChatMode = "private" | "publicAdmission";

export type StageState = {
  stage: string;
  status: "running" | "done" | "error";
  durationMs?: number;
  detail?: Record<string, unknown>;
};

export type ChatMessage = {
  id: string;
  role: "user" | "bot";
  content: string;
  status?: "pending" | "error";
  details?: ChatResult;
  stages?: StageState[];
  createdAt?: string;
};

export type ChatSession = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  sessionId: string;
  messages: ChatMessage[];
};

export type ChatHistoryState = {
  activeChatId: string | null;
  chats: ChatSession[];
};

export const DEFAULT_CHAT_TITLE = "Новый чат";
const LEGACY_DEFAULT_TITLES = new Set(["New chat", DEFAULT_CHAT_TITLE]);
const CHAT_STORAGE_VERSION = "v1";
const CHAT_STORAGE_PREFIX = "aqb_chat_history";
const PUBLIC_CONTACT_STORAGE_KEY = "aqb_public_admission_contact";
const REQUEST_HISTORY_LIMIT = 8;
const REQUEST_HISTORY_ITEM_CHARS = 700;
const MAX_STORED_CHATS = 50;

export const isDefaultTitle = (title: string) => LEGACY_DEFAULT_TITLES.has(title);

export const createId = (prefix: string) => `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export const createSessionId = () =>
  (typeof crypto !== "undefined" && "randomUUID" in crypto && crypto.randomUUID()) || createId("session");

export const buildStorageKey = (mode: ChatMode, sessionKey?: string | number | null) =>
  `${CHAT_STORAGE_PREFIX}_${CHAT_STORAGE_VERSION}_${mode}_${sessionKey ?? "guest"}`;

export const getPublicSessionIdFromUrl = () => {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  return (params.get("uuid") || params.get("session_id"))?.trim() || null;
};

/* ------------------------------------------------------------- storage */
export function loadChatState(key: string): ChatHistoryState | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ChatHistoryState;
    return parsed && Array.isArray(parsed.chats) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveChatState(key: string, state: ChatHistoryState) {
  try {
    // Never persist transient streaming state; trim very old chats.
    const chats = state.chats.slice(0, MAX_STORED_CHATS).map((chat) => ({
      ...chat,
      messages: chat.messages.map((message) =>
        message.status === "pending" ? { ...message, status: "error" as const, content: message.content || "Ответ был прерван." } : message,
      ),
    }));
    localStorage.setItem(key, JSON.stringify({ ...state, chats }));
  } catch {
    // Storage full or unavailable — chat still works in memory.
  }
}

export function getStoredPublicContact() {
  try {
    return localStorage.getItem(PUBLIC_CONTACT_STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function saveStoredPublicContact(value: string) {
  try {
    localStorage.setItem(PUBLIC_CONTACT_STORAGE_KEY, value);
  } catch {
    // Ignore storage errors.
  }
}

export const getContactType = (value: string) => {
  const normalized = value.trim();
  if (!normalized) return null;
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized)) return "email";
  if (/^\+?[\d\s().-]{7,}$/.test(normalized)) return "whatsapp_phone";
  return "contact";
};

export const isValidContact = (value: string) => {
  const type = getContactType(value);
  return type === "email" || type === "whatsapp_phone";
};

/* ------------------------------------------------------------ sessions */
export function createInitialChat(): ChatSession {
  const now = new Date().toISOString();
  return { id: createId("chat"), title: DEFAULT_CHAT_TITLE, createdAt: now, updatedAt: now, sessionId: createSessionId(), messages: [] };
}

export function normalizeChatState(state: ChatHistoryState, introMessage?: string): ChatHistoryState {
  const chats = (state.chats ?? []).map((chat) => ({
    ...chat,
    title: chat.title || DEFAULT_CHAT_TITLE,
    sessionId: chat.sessionId || createSessionId(),
    // Older versions stored the intro bubble as a message; it is UI-only now.
    messages: (chat.messages ?? []).filter((message) => !(introMessage && message.role === "bot" && message.content === introMessage)),
  }));
  const activeChatId =
    state.activeChatId && chats.some((chat) => chat.id === state.activeChatId) ? state.activeChatId : chats[0]?.id ?? null;
  return { activeChatId, chats };
}

export function buildChatTitle(message: string) {
  const trimmed = message.replace(/\s+/g, " ").trim();
  if (!trimmed) return DEFAULT_CHAT_TITLE;
  return trimmed.length > 80 ? `${trimmed.slice(0, 80)}…` : trimmed;
}

export function mapHistorySession(session: ChatHistorySession): ChatSession {
  return {
    id: `chat-${session.session_id}`,
    title: buildChatTitle(session.title || session.messages[0]?.content || ""),
    createdAt: session.created_at,
    updatedAt: session.updated_at,
    sessionId: session.session_id,
    messages: session.messages.map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      details: message.details,
      createdAt: message.created_at,
    })),
  };
}

export function groupChatsByDate(chats: ChatSession[]) {
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const day = 86_400_000;
  const groups: { label: string; chats: ChatSession[] }[] = [
    { label: "Сегодня", chats: [] },
    { label: "Вчера", chats: [] },
    { label: "Последние 7 дней", chats: [] },
    { label: "Ранее", chats: [] },
  ];
  for (const chat of chats) {
    const time = new Date(chat.updatedAt).getTime();
    if (time >= startOfToday.getTime()) groups[0].chats.push(chat);
    else if (time >= startOfToday.getTime() - day) groups[1].chats.push(chat);
    else if (time >= startOfToday.getTime() - 7 * day) groups[2].chats.push(chat);
    else groups[3].chats.push(chat);
  }
  return groups.filter((group) => group.chats.length);
}

/* ------------------------------------------------------------- history */
const compactHistoryContent = (value: string) => {
  const content = value.trim().replace(/\s+/g, " ");
  return content.length <= REQUEST_HISTORY_ITEM_CHARS ? content : `${content.slice(0, REQUEST_HISTORY_ITEM_CHARS - 1).trimEnd()}…`;
};

function compactHistoryDetails(details?: ChatResult): Record<string, unknown> | undefined {
  if (!details) return undefined;
  const compact: Record<string, unknown> = {};
  if (details.tool_data && typeof details.tool_data === "object") {
    const toolData = details.tool_data as Record<string, unknown>;
    const compactTool: Record<string, unknown> = {};
    if (toolData.request_slots && typeof toolData.request_slots === "object") compactTool.request_slots = toolData.request_slots;
    if (toolData.tool) compactTool.tool = toolData.tool;
    if (Object.keys(compactTool).length) compact.tool_data = compactTool;
  }
  for (const key of ["admission_state", "admission_profile", "classification", "orchestration"] as const) {
    if (details[key]) compact[key] = details[key];
  }
  return Object.keys(compact).length ? compact : undefined;
}

export function buildRequestHistory(messages: ChatMessage[]): ChatHistoryEntry[] {
  return messages
    .filter((message) => message.status !== "pending" && message.status !== "error" && message.content.trim())
    .slice(-REQUEST_HISTORY_LIMIT)
    .map((message) => {
      const details = compactHistoryDetails(message.details);
      return {
        role: message.role === "bot" ? "assistant" : "user",
        content: compactHistoryContent(stripHtml(message.content)),
        ...(details ? { details } : {}),
      };
    });
}

/* ----------------------------------------------------------- rendering */
const ALLOWED_TAGS = new Set([
  "P", "BR", "STRONG", "B", "EM", "I", "U", "UL", "OL", "LI", "H2", "H3", "H4", "TABLE", "THEAD", "TBODY",
  "TR", "TH", "TD", "BLOCKQUOTE", "CODE", "PRE", "A", "HR",
]);

const escapeHtml = (value: string) =>
  value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

/** Allow-list sanitizer: unknown tags are unwrapped, all attributes dropped (except safe links). */
function sanitizeHtml(value: string) {
  const doc = new DOMParser().parseFromString(`<div>${value}</div>`, "text/html");
  const root = doc.body.firstElementChild as HTMLElement | null;
  if (!root) return "";
  const walk = (node: Element) => {
    for (const child of Array.from(node.children)) {
      if (["SCRIPT", "STYLE", "IFRAME", "OBJECT", "EMBED", "NOSCRIPT", "TEMPLATE", "SVG", "MATH"].includes(child.tagName)) {
        child.remove();
        continue;
      }
      walk(child);
      if (!ALLOWED_TAGS.has(child.tagName)) {
        child.replaceWith(...Array.from(child.childNodes));
        continue;
      }
      const href = child.tagName === "A" ? child.getAttribute("href") ?? "" : "";
      for (const attr of Array.from(child.attributes)) child.removeAttribute(attr.name);
      if (child.tagName === "A" && /^(https?:|mailto:|tel:)/i.test(href.trim())) {
        child.setAttribute("href", href.trim());
        child.setAttribute("target", "_blank");
        child.setAttribute("rel", "noopener noreferrer");
      }
    }
  };
  walk(root);
  return root.innerHTML;
}

/** Light Markdown → HTML for models/tools that answer in Markdown instead of HTML. */
function renderLightMarkdown(value: string) {
  const blocks = value.split(/```/g);
  return blocks
    .map((block, index) => {
      if (index % 2 === 1) {
        const lines = block.replace(/^\n+|\n+$/g, "").split("\n");
        const code = /^[a-z0-9#+.-]{1,24}$/i.test((lines[0] ?? "").trim()) ? lines.slice(1).join("\n") : lines.join("\n");
        return `<pre><code>${escapeHtml(code)}</code></pre>`;
      }
      const lines = escapeHtml(block).split("\n");
      const html: string[] = [];
      let list: "ul" | "ol" | null = null;
      const closeList = () => {
        if (list) html.push(`</${list}>`);
        list = null;
      };
      for (const raw of lines) {
        const line = raw.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
        const bullet = line.match(/^\s*[-•*]\s+(.*)$/);
        const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
        if (bullet || numbered) {
          const kind = bullet ? "ul" : "ol";
          if (list !== kind) {
            closeList();
            html.push(`<${kind}>`);
            list = kind;
          }
          html.push(`<li>${(bullet ?? numbered)![1]}</li>`);
          continue;
        }
        closeList();
        const heading = line.match(/^#{1,4}\s+(.*)$/);
        if (heading) html.push(`<h3>${heading[1]}</h3>`);
        else if (line.trim()) html.push(`<p>${line}</p>`);
      }
      closeList();
      return html.join("");
    })
    .join("");
}

export function formatMessageContent(value: string) {
  if (!value) return "";
  if (/<\/?(p|br|ul|ol|li|strong|em|table|h[2-4]|blockquote|code|pre|a)\b[^>]*>/i.test(value)) {
    return sanitizeHtml(value.replace(/\n{2,}/g, "\n"));
  }
  return renderLightMarkdown(value);
}

export function stripHtml(value: string) {
  if (!/<[a-z][\s\S]*>/i.test(value)) return value;
  const doc = new DOMParser().parseFromString(value.replace(/<br\s*\/?>/gi, "\n").replace(/<\/(p|li|h\d|tr)>/gi, "\n"), "text/html");
  return (doc.body.textContent ?? "").replace(/\n{3,}/g, "\n\n").trim();
}

/* -------------------------------------------------------------- stages */
export const STAGE_LABELS: Record<string, string> = {
  intent: "Понимаю вопрос",
  retrieval: "Ищу в документах университета",
  policy: "Сверяюсь с регламентами",
  tutor: "Подбираю учебные материалы",
  admission: "Проверяю данные приёмной комиссии",
  dean: "Запрашиваю данные деканата",
  synthesis: "Формирую ответ",
  validator: "Проверяю факты",
};

export function applyStageEvent(stages: StageState[], event: ChatStageEvent): StageState[] {
  const next = stages.filter((item) => item.stage !== event.stage);
  next.push({ stage: event.stage, status: event.status, durationMs: event.duration_ms, detail: event.detail });
  return next;
}

export function formatDuration(ms?: number) {
  if (ms === undefined) return "";
  return ms < 1000 ? `${ms} мс` : `${(ms / 1000).toFixed(1)} с`;
}

/* ----------------------------------------------------------- analytics */
type AuthProfileLike = {
  telegram_id: number;
  person_id?: string | null;
  platonus_auth?: boolean;
  role?: string | null;
  fullname?: string | null;
  statusName?: string | null;
  email?: string | null;
};

export function buildChatAnalyticsMetadata(input: {
  profile: AuthProfileLike | null;
  isPublicAdmission: boolean;
  mode: ChatMode;
  message: string;
  sessionId: string;
  channel: string;
  context: { university: string; program: string; year: number; itp?: string };
  historyLength: number;
  publicContact?: string | null;
}) {
  const { profile, isPublicAdmission, mode, message, sessionId, channel, context, historyLength, publicContact } = input;
  const contact = publicContact?.trim() || null;
  const contactType = contact ? getContactType(contact) : null;
  return {
    channel,
    session_id: sessionId,
    request: {
      source: "academiq-question-web",
      origin: "website",
      endpoint: isPublicAdmission ? "/chat/public/admission/stream" : "/chat/stream",
      transport: "sse",
      chat_mode: mode,
      auth_mode: isPublicAdmission ? "anonymous" : "authenticated",
      is_authenticated: !isPublicAdmission,
      sent_at: new Date().toISOString(),
      message_length: message.length,
      history_length: historyLength,
    },
    context_snapshot: { ...context },
    user: isPublicAdmission
      ? {
          kind: "anonymous",
          contact: contact
            ? { value: contact, type: contactType, preferred_channel: contactType === "email" ? "email" : "whatsapp" }
            : null,
        }
      : {
          kind: "authenticated",
          telegram_id: profile?.telegram_id ?? null,
          person_id: profile?.person_id ?? null,
          role: profile?.role ?? null,
          platonus_auth: Boolean(profile?.platonus_auth),
          fullname: profile?.fullname ?? null,
          status_name: profile?.statusName ?? null,
          email: profile?.email ?? null,
        },
    page: {
      path: window.location.pathname,
      url: window.location.href,
      title: document.title || null,
      referrer: document.referrer || null,
    },
    client: {
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || null,
      locale: navigator.language || null,
      languages: [...navigator.languages],
      user_agent: navigator.userAgent || null,
      viewport: { width: window.innerWidth, height: window.innerHeight },
    },
  };
}
