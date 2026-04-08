import { useEffect, useMemo, useRef, useState } from "react";
import { apiClient } from "../api/client";
import {
  getChatHistory,
  getPublicChatHistory,
  streamChatMessage,
  streamPublicAdmissionMessage,
} from "../api/chat";
import type {
  ChatHistoryEntry,
  ChatHistorySession,
  ChatRequestPayload,
  ChatResult,
} from "../types";

const DEFAULT_PROFILE = {
  language: "ru",
  context: {
    university: "TAU",
    program: "ComputerScience",
    year: 2,
    itp: "ITP-2024",
  },
} as const;

const PUBLIC_ADMISSION_PROFILE = {
  language: "ru",
  context: {
    university: "TAU",
    program: "admission",
    year: 0,
    itp: "admissions-public",
  },
} as const;

type FakeChatMode = "private" | "publicAdmission";

type ChatMessage = {
  id: string;
  role: "user" | "bot";
  content: string;
  status?: "pending" | "error";
  details?: ChatResult;
};

const BOT_PLACEHOLDER = "Preparing response...";
const CHAT_VARIANTS = {
  private: {
    introMessage: `Ask your question about ${DEFAULT_PROFILE.context.university} and ${DEFAULT_PROFILE.context.itp}.`,
    title: "Academic Assistant",
    badge: "Chat",
    brand: "Academic Question Bot",
    searchPlaceholder: "Поиск в чатах",
    newChatLabel: "Новый чат",
    emptyTitle: "Задайте вопрос",
    composerPlaceholder: "Спросите Academic Assistant...",
    footnote: "Academic Question Bot может допускать ошибки. Проверяйте важную информацию.",
    quickActions: [
      { title: "Сбросить пароль", prompt: "Помоги сбросить пароль и восстановить доступ к аккаунту." },
      { title: "Когда сессия?", prompt: "Узнай, когда у меня сессия и какие даты экзаменов и зачетов." },
      { title: "Справка", prompt: "Сформируй текст заявления или запроса справки для деканата." },
      { title: "Статус заявки", prompt: "Проверь статус моей заявки и что еще нужно предоставить." },
    ],
  },
  publicAdmission: {
    introMessage: "Спросите про поступление в TAU: программы, стоимость, документы, проходные баллы или контакты приемной комиссии.",
    title: "Приемная комиссия TAU",
    badge: "Public",
    brand: "TAU Admissions AI",
    searchPlaceholder: "Поиск по диалогам",
    newChatLabel: "Новый диалог",
    emptyTitle: "Чат приемной комиссии",
    composerPlaceholder: "Напишите вопрос о поступлении...",
    footnote: "Ответы формируются по данным приемной комиссии TAU. Для критичных решений сверяйте информацию дополнительно.",
    quickActions: [
      { title: "Стоимость обучения", prompt: "Сколько стоит обучение в TAU и какие есть программы?" },
      { title: "Документы", prompt: "Какие документы нужны для поступления на бакалавриат?" },
      { title: "Проходные баллы", prompt: "Какие проходные баллы и требования для поступления?" },
      { title: "Контакты", prompt: "Как связаться с приемной комиссией и в какое время она работает?" },
    ],
  },
} as const;

type AuthProfile = {
  telegram_id: number;
  person_id?: string | null;
  platonus_auth?: boolean;
  role?: string | null;
  fullname?: string | null;
  statusName?: string | null;
  email?: string | null;
};

type ChatSession = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  sessionId: string;
  messages: ChatMessage[];
};

type ChatHistoryState = {
  activeChatId: string | null;
  chats: ChatSession[];
};

const DEFAULT_CHAT_TITLE = "New chat";
const CHAT_STORAGE_VERSION = "v1";
const CHAT_STORAGE_PREFIX = "aqb_chat_history";

const createId = (prefix: string) =>
  `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;

const createSessionId = () =>
  (typeof crypto !== "undefined" && "randomUUID" in crypto && crypto.randomUUID())
    || createId("session");

const createMessageId = (prefix: string) => createId(prefix);

const buildStorageKey = (mode: FakeChatMode, sessionKey?: string | number | null) =>
  `${CHAT_STORAGE_PREFIX}_${CHAT_STORAGE_VERSION}_${mode}_${sessionKey ?? "guest"}`;

const getPublicSessionId = () => {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get("uuid") || params.get("session_id");
  const normalized = sessionId?.trim();
  return normalized || null;
};

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const sanitizeHtml = (value: string) => {
  if (typeof window === "undefined") return value;
  const parser = new DOMParser();
  const document = parser.parseFromString(value, "text/html");
  ["script", "style", "iframe", "object", "embed", "link"].forEach((tag) => {
    document.querySelectorAll(tag).forEach((node) => node.remove());
  });
  document.querySelectorAll("*").forEach((node) => {
    Array.from(node.attributes).forEach((attr) => {
      const name = attr.name.toLowerCase();
      const value = attr.value.trim().toLowerCase();
      if (name.startsWith("on")) {
        node.removeAttribute(attr.name);
      }
      if ((name === "href" || name === "src") && value.startsWith("javascript:")) {
        node.removeAttribute(attr.name);
      }
    });
  });
  return document.body.innerHTML;
};

const truncateText = (value: string, maxLength: number) => {
  const text = value ?? "";
  if (text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(0, maxLength)).trimEnd()}...`;
};

const renderCodeFences = (value: string) => {
  const parts = value.split(/```/g);
  if (parts.length === 1) return escapeHtml(value).replace(/\n/g, "<br />");

  return parts
    .map((part, index) => {
      if (index % 2 === 0) {
        return escapeHtml(part).replace(/\n/g, "<br />");
      }
      const lines = part.replace(/^\n+|\n+$/g, "").split("\n");
      const first = (lines[0] ?? "").trim();
      const hasLanguage = /^[a-z0-9#+.-]{1,24}$/i.test(first);
      const code = (hasLanguage ? lines.slice(1) : lines).join("\n");
      return `<pre class="chat-code"><code>${escapeHtml(code)}</code></pre>`;
    })
    .join("");
};

const formatMessageContent = (value: string) => {
  if (/<\/?[a-z][\s\S]*>/i.test(value)) {
    return sanitizeHtml(value);
  }
  if (value.includes("```")) {
    return renderCodeFences(value);
  }
  return escapeHtml(value).replace(/\n/g, "<br />");
};

const buildChatTitle = (message: string) => {
  const trimmed = message.replace(/\s+/g, " ").trim();
  if (!trimmed) return DEFAULT_CHAT_TITLE;
  return trimmed.length > 100 ? `${trimmed.slice(0, 100)}...` : trimmed;
};

const createIntroMessage = (): ChatMessage => ({
  id: createMessageId("intro"),
  role: "bot",
  content: CHAT_VARIANTS.private.introMessage,
});

const createModeIntroMessage = (mode: FakeChatMode): ChatMessage => ({
  id: createMessageId("intro"),
  role: "bot",
  content: CHAT_VARIANTS[mode].introMessage,
});

const createInitialChat = (mode: FakeChatMode): ChatSession => {
  const now = new Date().toISOString();
  return {
    id: createId("chat"),
    title: DEFAULT_CHAT_TITLE,
    createdAt: now,
    updatedAt: now,
    sessionId: createSessionId(),
    messages: [createModeIntroMessage(mode)],
  };
};

const normalizeChatState = (state: ChatHistoryState, mode: FakeChatMode): ChatHistoryState => {
  const chats = (state.chats ?? []).map((chat) => {
    const messages: ChatMessage[] = chat.messages?.length
      ? chat.messages
      : [createModeIntroMessage(mode)];
    return {
      ...chat,
      title: chat.title || DEFAULT_CHAT_TITLE,
      sessionId: chat.sessionId || createSessionId(),
      messages,
    };
  });
  const activeChatId =
    state.activeChatId && chats.some((chat) => chat.id === state.activeChatId)
      ? state.activeChatId
      : chats[0]?.id ?? null;
  return { activeChatId, chats };
};

const mapHistorySession = (session: ChatHistorySession): ChatSession => {
  const messages: ChatMessage[] = session.messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
  }));
  return {
    id: `chat-${session.session_id}`,
    title: buildChatTitle(session.title || session.messages[0]?.content || ""),
    createdAt: session.created_at,
    updatedAt: session.updated_at,
    sessionId: session.session_id,
    messages: messages.length ? messages : [createModeIntroMessage("private")],
  };
};

const buildRequestHistory = (
  messages: ChatMessage[],
  introMessage: string,
  pendingMessage?: ChatMessage,
): ChatHistoryEntry[] => {
  const source = pendingMessage ? [...messages, pendingMessage] : messages;
  return source
    .filter((message) => {
      if (message.content === introMessage) return false;
      if (message.status === "pending") return false;
      return true;
    })
    .map((message) => ({
      role: message.role === "bot" ? "assistant" : "user",
      content: message.content,
    }));
};

const loadChatState = (key: string): ChatHistoryState | null => {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as ChatHistoryState;
    if (!parsed || !Array.isArray(parsed.chats)) return null;
    return parsed;
  } catch {
    return null;
  }
};

const saveChatState = (key: string, state: ChatHistoryState) => {
  try {
    localStorage.setItem(key, JSON.stringify(state));
  } catch {
    // Ignore storage write errors.
  }
};

const formatChatDate = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const buildChatAnalyticsMetadata = ({
  profile,
  isPublicAdmission,
  mode,
  message,
  sessionId,
  channel,
  context,
  historyLength,
}: {
  profile: AuthProfile | null;
  isPublicAdmission: boolean;
  mode: FakeChatMode;
  message: string;
  sessionId: string;
  channel: string;
  context: {
    university: string;
    program: string;
    year: number;
    itp?: string;
  };
  historyLength: number;
}) => {
  const now = new Date().toISOString();
  const endpoint = isPublicAdmission ? "/chat/public/admission/stream" : "/chat/stream";
  const path = typeof window !== "undefined" ? window.location.pathname : null;
  const href = typeof window !== "undefined" ? window.location.href : null;
  const referrer = typeof document !== "undefined" ? document.referrer || null : null;
  const title = typeof document !== "undefined" ? document.title || null : null;
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  const locale = typeof navigator !== "undefined" ? navigator.language || null : null;
  const languages = typeof navigator !== "undefined" ? [...navigator.languages] : [];
  const userAgent = typeof navigator !== "undefined" ? navigator.userAgent || null : null;
  const platform = typeof navigator !== "undefined" ? navigator.platform || null : null;
  const viewport = typeof window !== "undefined"
    ? { width: window.innerWidth, height: window.innerHeight }
    : null;
  const screenSize = typeof window !== "undefined"
    ? { width: window.screen.width, height: window.screen.height }
    : null;

  return {
    channel,
    session_id: sessionId,
    request: {
      source: "academiq-question-web",
      origin: "website",
      endpoint,
      transport: "sse",
      chat_mode: mode,
      auth_mode: isPublicAdmission ? "anonymous" : "authenticated",
      is_authenticated: !isPublicAdmission,
      sent_at: now,
      message_length: message.length,
      history_length: historyLength,
    },
    context_snapshot: {
      university: context.university,
      program: context.program,
      year: context.year,
      itp: context.itp,
    },
    user: isPublicAdmission
      ? { kind: "anonymous" }
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
      path,
      url: href,
      title,
      referrer,
    },
    client: {
      timezone,
      locale,
      languages,
      user_agent: userAgent,
      platform,
      viewport,
      screen: screenSize,
    },
  };
};

const QUICK_ACTIONS = [
  { title: "Сбросить пароль", prompt: "Помоги сбросить пароль и восстановить доступ к аккаунту." },
  { title: "Когда сессия?", prompt: "Узнай, когда у меня сессия и какие даты экзаменов/зачётов." },
  { title: "Справка/подтверждение", prompt: "Сформируй текст заявления/запроса справки для деканата." },
  { title: "Статус заявки", prompt: "Проверь статус моей заявки и что ещё нужно предоставить." },
] as const;

export function FakeChat({ mode = "private" }: { mode?: FakeChatMode }) {
  const config = CHAT_VARIANTS[mode];
  const isPublicAdmission = mode === "publicAdmission";
  const publicSessionId = isPublicAdmission ? getPublicSessionId() : null;
  const profileConfig = isPublicAdmission ? PUBLIC_ADMISSION_PROFILE : DEFAULT_PROFILE;
  const [inputValue, setInputValue] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [profile, setProfile] = useState<AuthProfile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [storageKey, setStorageKey] = useState(() => buildStorageKey(mode, publicSessionId));
  const [highlightedChatId, setHighlightedChatId] = useState<string | null>(null);
  const [searchValue, setSearchValue] = useState("");
  const [openChatMenuId, setOpenChatMenuId] = useState<string | null>(null);
  const [propertiesChatId, setPropertiesChatId] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const highlightTimeoutRef = useRef<number | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const draftSessionIdRef = useRef<string>(publicSessionId ?? createSessionId());
  const [chatState, setChatState] = useState<ChatHistoryState>(() => {
    const empty: ChatHistoryState = { activeChatId: null, chats: [] };
    if (typeof window === "undefined") return empty;
    const stored = loadChatState(buildStorageKey(mode, publicSessionId));
    return stored ? normalizeChatState(stored, mode) : empty;
  });
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const activeChat = useMemo(() => {
    const active =
      chatState.chats.find((chat) => chat.id === chatState.activeChatId)
      ?? chatState.chats[0];
    return active ?? null;
  }, [chatState]);

  const visibleMessages = useMemo(() => {
    const messages = activeChat?.messages ?? [];
    return messages.filter(
      (message) => !(message.role === "bot" && message.content === config.introMessage),
    );
  }, [activeChat?.messages, config.introMessage]);

  const hasUserMessages = useMemo(() => {
    return visibleMessages.some((message) => message.role === "user");
  }, [visibleMessages]);

  const sortedChats = useMemo(() => {
    return [...chatState.chats].sort(
      (first, second) =>
        new Date(second.updatedAt).getTime() - new Date(first.updatedAt).getTime()
    );
  }, [chatState.chats]);

  const filteredChats = useMemo(() => {
    const query = searchValue.trim().toLowerCase();
    if (!query) return sortedChats;
    return sortedChats.filter((chat) => {
      const titleMatch = chat.title.toLowerCase().includes(query);
      const lastMessage = chat.messages[chat.messages.length - 1];
      const preview = lastMessage?.content ?? "";
      return titleMatch || preview.toLowerCase().includes(query);
    });
  }, [searchValue, sortedChats]);

  const requestMeta = useMemo(() => {
    return {
      language: profileConfig.language,
      channel: isPublicAdmission ? "public_web" : "web",
      session: activeChat?.sessionId ?? draftSessionIdRef.current,
      university: profileConfig.context.university,
      program: profileConfig.context.program,
      itp: profileConfig.context.itp,
    };
  }, [activeChat?.sessionId, isPublicAdmission, profileConfig]);

  const propertiesChat = useMemo(() => {
    if (!propertiesChatId) return null;
    return chatState.chats.find((chat) => chat.id === propertiesChatId) ?? null;
  }, [chatState.chats, propertiesChatId]);

  useEffect(() => {
    if (isPublicAdmission) {
      setStorageKey(buildStorageKey(mode, publicSessionId));
      return;
    }
    if (profile?.telegram_id) {
      setStorageKey(buildStorageKey(mode, profile.telegram_id));
    }
  }, [isPublicAdmission, mode, profile?.telegram_id, publicSessionId]);

  useEffect(() => {
    if (isPublicAdmission) return;
    if (!profile?.telegram_id) return;
    let active = true;
    getChatHistory()
      .then((response) => {
        if (!active || !response.sessions.length) return;
        const sessions = response.sessions.map(mapHistorySession);
        const nextState = normalizeChatState({
          activeChatId: sessions[0].id,
          chats: sessions,
        }, mode);
        setChatState(nextState);
      })
      .catch(() => {
        // Ignore history loading errors.
      });
    return () => {
      active = false;
    };
  }, [isPublicAdmission, mode, profile?.telegram_id]);

  useEffect(() => {
    if (!isPublicAdmission) return;
    if (!publicSessionId) return;
    let active = true;
    getPublicChatHistory(publicSessionId)
      .then((response) => {
        if (!active || !response.session) return;
        const session = mapHistorySession(response.session);
        draftSessionIdRef.current = response.session.session_id;
        setChatState(
          normalizeChatState(
            {
              activeChatId: session.id,
              chats: [session],
            },
            mode,
          ),
        );
      })
      .catch(() => {
        // Ignore public history loading errors and fall back to local state.
      });
    return () => {
      active = false;
    };
  }, [isPublicAdmission, mode, publicSessionId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = loadChatState(storageKey);
    if (stored) {
      setChatState(normalizeChatState(stored, mode));
      return;
    }
    const guestKey = buildStorageKey(mode, null);
    if (storageKey !== guestKey) {
      const guestState = loadChatState(guestKey);
      if (guestState) {
        saveChatState(storageKey, guestState);
        setChatState(normalizeChatState(guestState, mode));
        return;
      }
    }
    const nextState: ChatHistoryState = { activeChatId: null, chats: [] };
    saveChatState(storageKey, nextState);
    setChatState(nextState);
  }, [mode, storageKey]);

  useEffect(() => {
    saveChatState(storageKey, normalizeChatState(chatState, mode));
  }, [chatState, mode, storageKey]);

  useEffect(() => {
    if (isPublicAdmission) {
      setProfile(null);
      setProfileError(null);
      return;
    }
    let active = true;
    apiClient
      .get<{
        status: string;
        user: {
          telegram_id: number;
          person_id?: string | null;
          platonus_auth?: boolean;
          role?: string | null;
          fullname?: string | null;
          statusName?: string | null;
          email?: string | null;
        };
      }>(
        "/auth/me",
      )
      .then((response) => {
        if (active) {
          setProfile({
            telegram_id: response.user.telegram_id,
            person_id: response.user.person_id ?? null,
            platonus_auth: response.user.platonus_auth ?? false,
            role: response.user.role ?? null,
            fullname: response.user.fullname ?? null,
            statusName: response.user.statusName ?? null,
            email: response.user.email ?? null,
          });
        }
      })
      .catch((error) => {
        if (active) {
          const message =
            error instanceof Error ? error.message : "Failed to load profile.";
          setProfileError(message);
        }
      });
    return () => {
      active = false;
    };
  }, [isPublicAdmission]);

  useEffect(() => {
    return () => {
      if (highlightTimeoutRef.current) {
        window.clearTimeout(highlightTimeoutRef.current);
      }
      if (streamAbortRef.current) {
        streamAbortRef.current.abort();
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeChat?.messages.length]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!openChatMenuId) return;

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (!target) return;
      if (target.closest("[data-chat-menu]")) return;
      setOpenChatMenuId(null);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpenChatMenuId(null);
      }
    };

    window.addEventListener("mousedown", handlePointerDown, true);
    window.addEventListener("keydown", handleKeyDown, true);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown, true);
      window.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [openChatMenuId]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!propertiesChatId) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setPropertiesChatId(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [propertiesChatId]);

  const replaceMessage = (chatId: string, id: string, data: Partial<ChatMessage>) => {
    setChatState((prev) => {
      const normalized = normalizeChatState(prev, mode);
      const chats = normalized.chats.map((chat) => {
        if (chat.id !== chatId) return chat;
        const messages = chat.messages.map((message) =>
          message.id === id ? { ...message, ...data } : message
        );
        return { ...chat, messages };
      });
      return { ...normalized, chats };
    });
  };

  const toggleDetails = (id: string) => {
    setExpandedId((current) => (current === id ? null : id));
  };

  const focusComposer = () => {
    window.setTimeout(() => inputRef.current?.focus(), 0);
  };

  const abortStream = () => {
    if (streamAbortRef.current) {
      streamAbortRef.current.abort();
      streamAbortRef.current = null;
    }
    setIsStreaming(false);
  };

  const handleNewChat = () => {
    abortStream();
    const chat = createInitialChat(mode);
    setChatState((prev) => ({
      activeChatId: chat.id,
      chats: [chat, ...prev.chats],
    }));
    setHighlightedChatId(chat.id);
    draftSessionIdRef.current = createSessionId();
    if (highlightTimeoutRef.current) {
      window.clearTimeout(highlightTimeoutRef.current);
    }
    highlightTimeoutRef.current = window.setTimeout(() => {
      setHighlightedChatId(null);
    }, 700);
    setExpandedId(null);
    setInputValue("");
    focusComposer();
  };

  const handleSelectChat = (chatId: string) => {
    abortStream();
    setChatState((prev) => ({ ...prev, activeChatId: chatId }));
    setExpandedId(null);
    setOpenChatMenuId(null);
    focusComposer();
  };

  const handleSend = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    if (isStreaming) return;
    if (!isPublicAdmission && !profile?.telegram_id) {
      const chatId = activeChat?.id ?? createId("chat");
      const errorMessage: ChatMessage = {
        id: createMessageId("system"),
        role: "bot",
        content: "Telegram profile not found. Please re-login.",
        status: "error",
      };
      setChatState((prev) => {
        const normalized = normalizeChatState(prev, mode);
        const chatExists = normalized.chats.some((chat) => chat.id === chatId);
        const chats = chatExists
          ? normalized.chats.map((chat) =>
            chat.id === chatId
              ? {
                ...chat,
                messages: [...chat.messages, errorMessage],
                updatedAt: new Date().toISOString(),
              }
              : chat
          )
          : [
            {
              ...createInitialChat(mode),
              id: chatId,
              messages: [createModeIntroMessage(mode), errorMessage],
            },
            ...normalized.chats,
          ];
        return { ...normalized, chats, activeChatId: chatId };
      });
      return;
    }

    const userMessage: ChatMessage = {
      id: createMessageId("user"),
      role: "user",
      content: trimmed,
    };
    const botMessageId = createMessageId("bot");
    const placeholderMessage: ChatMessage = {
      id: botMessageId,
      role: "bot",
      content: "",
      status: "pending",
    };

    const activeChatId = activeChat?.id ?? createId("chat");
    const newChatSessionId = activeChat?.sessionId ?? draftSessionIdRef.current;
    setChatState((prev) => {
      const normalized = normalizeChatState(prev, mode);
      const now = new Date().toISOString();
      const chats = normalized.chats.map((chat) => {
        if (chat.id !== activeChatId) return chat;
        const title =
          chat.title === DEFAULT_CHAT_TITLE ? buildChatTitle(trimmed) : chat.title;
        return {
          ...chat,
          title,
          updatedAt: now,
          messages: [...chat.messages, userMessage, placeholderMessage],
        };
      });
      const hasActive = chats.some((chat) => chat.id === activeChatId);
      return {
        ...normalized,
        activeChatId: activeChatId,
        chats: hasActive
          ? chats
          : [
            {
              ...createInitialChat(mode),
              id: activeChatId,
              sessionId: newChatSessionId,
              title: buildChatTitle(trimmed),
              messages: [
                createModeIntroMessage(mode),
                userMessage,
                placeholderMessage,
              ],
            },
            ...chats,
          ],
      };
    });
    setInputValue("");
    if (!activeChat?.id) {
      draftSessionIdRef.current = createSessionId();
    }

    const requestHistory = buildRequestHistory(
      activeChat?.messages ?? [],
      config.introMessage,
      userMessage,
    );

    const payload: ChatRequestPayload = {
      user_id: isPublicAdmission ? undefined : profile?.telegram_id ?? 0,
      telegram_id: isPublicAdmission ? undefined : profile?.telegram_id,
      person_id: isPublicAdmission ? undefined : profile?.person_id ?? undefined,
      uuid: isPublicAdmission ? requestMeta.session : undefined,
      message: trimmed,
      language: profileConfig.language,
      context: profileConfig.context,
      metadata: buildChatAnalyticsMetadata({
        profile,
        isPublicAdmission,
        mode,
        message: trimmed,
        sessionId: requestMeta.session,
        channel: requestMeta.channel,
        context: profileConfig.context,
        historyLength: requestHistory.length,
      }),
      history: requestHistory,
    };

    const controller = new AbortController();
    streamAbortRef.current = controller;
    setIsStreaming(true);

    let streamedText = "";
    let pendingDelta = "";
    let flushTimeout: number | null = null;

    const flushStream = () => {
      flushTimeout = null;
      if (!pendingDelta) return;
      streamedText += pendingDelta;
      pendingDelta = "";
      replaceMessage(activeChatId, botMessageId, {
        content: streamedText || BOT_PLACEHOLDER,
        status: "pending",
      });
    };

    const scheduleFlush = () => {
      if (flushTimeout) return;
      flushTimeout = window.setTimeout(flushStream, 40);
    };

    const streamRequest = isPublicAdmission ? streamPublicAdmissionMessage : streamChatMessage;

    streamRequest(
      payload,
      {
        onDelta: (delta) => {
          pendingDelta += delta;
          scheduleFlush();
        },
        onError: (error) => {
          if (flushTimeout) {
            window.clearTimeout(flushTimeout);
            flushTimeout = null;
          }
          replaceMessage(activeChatId, botMessageId, {
            content: error || "Request failed.",
            status: "error",
          });
        },
      },
      controller.signal,
    )
      .then((response) => {
        if (flushTimeout) {
          window.clearTimeout(flushTimeout);
          flushTimeout = null;
        }
        if (pendingDelta) {
          streamedText += pendingDelta;
          pendingDelta = "";
        }
        const result = response.result;
        replaceMessage(activeChatId, botMessageId, {
          content: result.final_answer || streamedText || "No answer from the agent.",
          status: undefined,
          details: result,
        });
      })
      .catch((error) => {
        if (error instanceof Error && error.name === "AbortError") {
          return;
        }
        if (flushTimeout) {
          window.clearTimeout(flushTimeout);
          flushTimeout = null;
        }
        replaceMessage(activeChatId, botMessageId, {
          content: error instanceof Error ? error.message : "Request failed.",
          status: "error",
        });
      })
      .finally(() => {
        if (flushTimeout) {
          window.clearTimeout(flushTimeout);
          flushTimeout = null;
        }
        if (streamAbortRef.current === controller) {
          streamAbortRef.current = null;
        }
        setIsStreaming(false);
      });
  };

  return (
    <section className="chat-shell">
      <aside className="chat-sidebar">
        <div className="chat-sidebar__content">
          <div className="chat-sidebar__brand">
            <span className="chat-sidebar__logo" aria-hidden="true">AQB</span>
            <span className="chat-sidebar__brand-text">{config.brand}</span>
          </div>
          <div className="chat-sidebar__primary">
            <button
              type="button"
              className="chat-sidebar__new-chat"
              onClick={handleNewChat}
            >
              <span className="chat-sidebar__new-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="8" fill="none" />
                  <line x1="12" y1="8.5" x2="12" y2="15.5" />
                  <line x1="8.5" y1="12" x2="15.5" y2="12" />
                </svg>
              </span>
              Новый чат
            </button>
            <label className="chat-sidebar__search">
              <span className="chat-sidebar__search-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <circle cx="11" cy="11" r="6" fill="none" />
                  <line x1="15.5" y1="15.5" x2="20" y2="20" />
                </svg>
              </span>
              <input
                type="search"
                value={searchValue}
                onChange={(event) => setSearchValue(event.target.value)}
                placeholder={config.searchPlaceholder}
              />
            </label>
          </div>
          <div className="chat-sidebar__list">
            {filteredChats.map((chat) => {
              return (
                <div
                  key={chat.id}
                  className={`chat-list-item${
                    chat.id === activeChat?.id ? " active" : ""
                  }${chat.id === highlightedChatId ? " chat-list-item--new" : ""}`}
                >
                  <button
                    type="button"
                    className="chat-list-item__main"
                    onClick={() => handleSelectChat(chat.id)}
                    title={chat.title}
                  >
                    <span className="chat-list-item__title">
                      {truncateText(chat.title, 100)}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="icon-button icon-button--ghost chat-list-item__menu-button"
                    aria-label="Chat options"
                    data-chat-menu
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      setOpenChatMenuId((current) => (current === chat.id ? null : chat.id));
                    }}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <circle cx="6" cy="12" r="1.5" />
                      <circle cx="12" cy="12" r="1.5" />
                      <circle cx="18" cy="12" r="1.5" />
                    </svg>
                  </button>
                  {openChatMenuId === chat.id ? (
                    <div className="chat-list-item__menu" role="menu" data-chat-menu>
                      <button
                        type="button"
                        className="chat-list-item__menu-item"
                        role="menuitem"
                        onClick={() => {
                          setOpenChatMenuId(null);
                          setPropertiesChatId(chat.id);
                        }}
                      >
                        Properties
                      </button>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      </aside>

      <section className="fake-chat">
        <header className="fake-chat__header chat-topbar">
          <div className="chat-topbar__title">
            <span className="chat-topbar__badge">{config.badge}</span>
            <span className="chat-topbar__name">{config.title}</span>
          </div>
        </header>

        {!hasUserMessages ? (
          <div className="chat-empty">
            <h1 className="chat-empty__title">{config.emptyTitle}</h1>
            <div className="chat-composer chat-composer--center" role="form" aria-label="Chat composer">
              {profileError ? <p className="error chat-composer__error">{profileError}</p> : null}
              <div className="chat-composer__bar">
                <textarea
                  className="chat-composer__textarea"
                  placeholder={config.composerPlaceholder}
                  value={inputValue}
                  onChange={(event) => setInputValue(event.target.value)}
                  rows={2}
                  ref={inputRef}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <button
                  type="button"
                  className="icon-button chat-composer__icon"
                  onClick={handleSend}
                  disabled={!inputValue.trim() || isStreaming}
                  aria-label="Send"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M4 12h14" fill="none" />
                    <path d="M12 5l7 7-7 7" fill="none" />
                  </svg>
                </button>
              </div>
              <p className="chat-composer__footnote">
                {config.footnote}
              </p>
            </div>
            <div className="chat-suggestions" aria-label="Quick actions">
              {config.quickActions.map((item) => (
                <button
                  key={item.title}
                  type="button"
                  className="chat-suggestion"
                  onClick={() => {
                    setInputValue(item.prompt);
                    focusComposer();
                  }}
                >
                  <span className="chat-suggestion__title">{item.title}</span>
                  <span className="chat-suggestion__subtitle">{item.prompt}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <div
              className={`chat-window${
                activeChat?.id === highlightedChatId ? " chat-window--new" : ""
              }`}
            >
              <div className="chat-messages">
                {visibleMessages.map((message) => (
                  <article
                    key={message.id}
                    className={`chat-message ${message.role === "user" ? "user" : "bot"}${
                      message.status === "pending" ? " pending" : ""
                    }${message.status === "error" ? " error" : ""}`}
                    onClick={() => {
                      if (message.role === "bot" && message.details) {
                        toggleDetails(message.id);
                      }
                    }}
                    role={message.role === "bot" && message.details ? "button" : undefined}
                    tabIndex={message.role === "bot" && message.details ? 0 : undefined}
                    onKeyDown={(event) => {
                      if (
                        event.key === "Enter" &&
                        message.role === "bot" &&
                        message.details
                      ) {
                        event.preventDefault();
                        toggleDetails(message.id);
                      }
                    }}
                  >
                    <div
                      className="chat-message__content"
                      dangerouslySetInnerHTML={{
                        __html: formatMessageContent(message.content),
                      }}
                    />
                    {message.role === "bot" && message.details ? (
                      <div
                        className={`chat-message__details ${
                          expandedId === message.id ? "open" : ""
                        }`}
                      >
                        <span className="chat-message__details-label">Details JSON</span>
                        <pre>{JSON.stringify(message.details, null, 2)}</pre>
                      </div>
                    ) : null}
                  </article>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>

            <div className="chat-composer chat-composer--bottom chat-composer--sticky" role="form" aria-label="Chat composer">
              {profileError ? <p className="error chat-composer__error">{profileError}</p> : null}
              <div className="chat-composer__bar">
                <textarea
                  className="chat-composer__textarea"
                  placeholder={config.composerPlaceholder}
                  value={inputValue}
                  onChange={(event) => setInputValue(event.target.value)}
                  rows={2}
                  ref={inputRef}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <button
                  type="button"
                  className="icon-button chat-composer__icon"
                  onClick={handleSend}
                  disabled={!inputValue.trim() || isStreaming}
                  aria-label="Send"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M4 12h14" fill="none" />
                    <path d="M12 5l7 7-7 7" fill="none" />
                  </svg>
                </button>
              </div>
              <p className="chat-composer__footnote">
                {config.footnote}
              </p>
            </div>
          </>
        )}
      </section>

      {propertiesChat ? (
        <div
          className="chat-properties-modal__overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Chat properties"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setPropertiesChatId(null);
            }
          }}
        >
          <div className="chat-properties-modal__panel">
            <div className="chat-properties-modal__header">
              <h3>Chat properties</h3>
              <button
                type="button"
                className="icon-button icon-button--ghost"
                onClick={() => setPropertiesChatId(null)}
                aria-label="Close"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <line x1="6" y1="6" x2="18" y2="18" />
                  <line x1="18" y1="6" x2="6" y2="18" />
                </svg>
              </button>
            </div>
            <dl className="chat-properties-modal__grid">
              <dt>Title</dt>
              <dd>{propertiesChat.title}</dd>
              <dt>Chat ID</dt>
              <dd>{propertiesChat.id}</dd>
              <dt>Session ID</dt>
              <dd>{propertiesChat.sessionId}</dd>
              <dt>Created</dt>
              <dd>{formatChatDate(propertiesChat.createdAt)}</dd>
              <dt>Updated</dt>
              <dd>{formatChatDate(propertiesChat.updatedAt)}</dd>
              <dt>Messages</dt>
              <dd>{propertiesChat.messages.length}</dd>
            </dl>
          </div>
        </div>
      ) : null}
    </section>
  );
}
