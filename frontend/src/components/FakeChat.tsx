import { useEffect, useMemo, useRef, useState } from "react";
import { apiClient } from "../api/client";
import { getChatHistory, streamChatMessage } from "../api/chat";
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

type ChatMessage = {
  id: string;
  role: "user" | "bot";
  content: string;
  status?: "pending" | "error";
  details?: ChatResult;
};

const BOT_PLACEHOLDER = "Preparing response...";
const INTRO_MESSAGE = `Ask your question about ${DEFAULT_PROFILE.context.university} and ${DEFAULT_PROFILE.context.itp}.`;

type AuthProfile = {
  telegram_id: number;
  person_id?: string | null;
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

const buildStorageKey = (telegramId?: number | null) =>
  `${CHAT_STORAGE_PREFIX}_${CHAT_STORAGE_VERSION}_${telegramId ?? "guest"}`;

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
  content: INTRO_MESSAGE,
});

const createInitialChat = (): ChatSession => {
  const now = new Date().toISOString();
  return {
    id: createId("chat"),
    title: DEFAULT_CHAT_TITLE,
    createdAt: now,
    updatedAt: now,
    sessionId: createSessionId(),
    messages: [createIntroMessage()],
  };
};

const normalizeChatState = (state: ChatHistoryState): ChatHistoryState => {
  const chats = (state.chats ?? []).map((chat) => {
    const messages: ChatMessage[] = chat.messages?.length
      ? chat.messages
      : [createIntroMessage()];
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
    messages: messages.length ? messages : [createIntroMessage()],
  };
};

const buildRequestHistory = (messages: ChatMessage[], pendingMessage?: ChatMessage): ChatHistoryEntry[] => {
  const source = pendingMessage ? [...messages, pendingMessage] : messages;
  return source
    .filter((message) => {
      if (message.content === INTRO_MESSAGE) return false;
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
    return normalizeChatState(parsed);
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

const QUICK_ACTIONS = [
  { title: "Сбросить пароль", prompt: "Помоги сбросить пароль и восстановить доступ к аккаунту." },
  { title: "Когда сессия?", prompt: "Узнай, когда у меня сессия и какие даты экзаменов/зачётов." },
  { title: "Справка/подтверждение", prompt: "Сформируй текст заявления/запроса справки для деканата." },
  { title: "Статус заявки", prompt: "Проверь статус моей заявки и что ещё нужно предоставить." },
] as const;

export function FakeChat() {
  const [inputValue, setInputValue] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [profile, setProfile] = useState<AuthProfile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [storageKey, setStorageKey] = useState(() => buildStorageKey(null));
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [highlightedChatId, setHighlightedChatId] = useState<string | null>(null);
  const [searchValue, setSearchValue] = useState("");
  const [openChatMenuId, setOpenChatMenuId] = useState<string | null>(null);
  const [propertiesChatId, setPropertiesChatId] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const searchRef = useRef<HTMLInputElement | null>(null);
  const highlightTimeoutRef = useRef<number | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const draftSessionIdRef = useRef<string>(createSessionId());
  const [chatState, setChatState] = useState<ChatHistoryState>(() => {
    const empty: ChatHistoryState = { activeChatId: null, chats: [] };
    if (typeof window === "undefined") return empty;
    const stored = loadChatState(buildStorageKey(null));
    return stored ?? empty;
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
      (message) => !(message.role === "bot" && message.content === INTRO_MESSAGE),
    );
  }, [activeChat?.messages]);

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
      language: DEFAULT_PROFILE.language,
      channel: "web",
      session: activeChat?.sessionId ?? draftSessionIdRef.current,
      university: DEFAULT_PROFILE.context.university,
      program: DEFAULT_PROFILE.context.program,
      itp: DEFAULT_PROFILE.context.itp,
    };
  }, [activeChat?.sessionId]);

  const propertiesChat = useMemo(() => {
    if (!propertiesChatId) return null;
    return chatState.chats.find((chat) => chat.id === propertiesChatId) ?? null;
  }, [chatState.chats, propertiesChatId]);

  useEffect(() => {
    if (profile?.telegram_id) {
      setStorageKey(buildStorageKey(profile.telegram_id));
    }
  }, [profile?.telegram_id]);

  useEffect(() => {
    if (!profile?.telegram_id) return;
    let active = true;
    getChatHistory()
      .then((response) => {
        if (!active || !response.sessions.length) return;
        const sessions = response.sessions.map(mapHistorySession);
        const nextState = normalizeChatState({
          activeChatId: sessions[0].id,
          chats: sessions,
        });
        setChatState(nextState);
      })
      .catch(() => {
        // Ignore history loading errors.
      });
    return () => {
      active = false;
    };
  }, [profile?.telegram_id]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = loadChatState(storageKey);
    if (stored) {
      setChatState(stored);
      return;
    }
    const guestKey = buildStorageKey(null);
    if (storageKey !== guestKey) {
      const guestState = loadChatState(guestKey);
      if (guestState) {
        saveChatState(storageKey, guestState);
        setChatState(guestState);
        return;
      }
    }
    const nextState: ChatHistoryState = { activeChatId: null, chats: [] };
    saveChatState(storageKey, nextState);
    setChatState(nextState);
  }, [storageKey]);

  useEffect(() => {
    saveChatState(storageKey, normalizeChatState(chatState));
  }, [chatState, storageKey]);

  useEffect(() => {
    let active = true;
    apiClient
      .get<{ status: string; user: { telegram_id: number; person_id?: string | null } }>(
        "/auth/me",
      )
      .then((response) => {
        if (active) {
          setProfile({
            telegram_id: response.user.telegram_id,
            person_id: response.user.person_id ?? null,
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
  }, []);

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
      const normalized = normalizeChatState(prev);
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
    const chat = createInitialChat();
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
    if (!profile?.telegram_id) {
      const chatId = activeChat?.id ?? createId("chat");
      const errorMessage: ChatMessage = {
        id: createMessageId("system"),
        role: "bot",
        content: "Telegram profile not found. Please re-login.",
        status: "error",
      };
      setChatState((prev) => {
        const normalized = normalizeChatState(prev);
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
              ...createInitialChat(),
              id: chatId,
              messages: [createIntroMessage(), errorMessage],
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
      const normalized = normalizeChatState(prev);
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
              ...createInitialChat(),
              id: activeChatId,
              sessionId: newChatSessionId,
              title: buildChatTitle(trimmed),
              messages: [
                createIntroMessage(),
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

    const controller = new AbortController();
    streamAbortRef.current = controller;
    setIsStreaming(true);

    const payload: ChatRequestPayload = {
      user_id: profile?.telegram_id ?? 0,
      telegram_id: profile?.telegram_id,
      person_id: profile?.person_id ?? undefined,
      message: trimmed,
      language: DEFAULT_PROFILE.language,
      context: DEFAULT_PROFILE.context,
      metadata: {
        channel: "web",
        session_id: requestMeta.session,
      },
      history: buildRequestHistory(activeChat?.messages ?? [], userMessage),
    };

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

    streamChatMessage(
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
    <section className={`chat-shell${isSidebarOpen ? "" : " chat-shell--collapsed"}`}>
      <aside className="chat-sidebar" aria-hidden={!isSidebarOpen}>
        <div className="chat-sidebar__content">
          <div className="chat-sidebar__brand">
            <span className="chat-sidebar__logo" aria-hidden="true">AQB</span>
            <span className="chat-sidebar__brand-text">Academic Question Bot</span>
          </div>
          <div className="chat-sidebar__header">
            <button
              type="button"
              className="icon-button icon-button--ghost"
              onClick={() => setIsSidebarOpen(false)}
              aria-label="Collapse history"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="3" y="5" width="18" height="14" rx="3" fill="none" />
                <line x1="9" y1="5" x2="9" y2="19" />
              </svg>
            </button>
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
                ref={searchRef}
                type="search"
                value={searchValue}
                onChange={(event) => setSearchValue(event.target.value)}
                placeholder="Поиск в чатах"
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
        <div className="chat-sidebar__icons" aria-hidden={isSidebarOpen}>
          <button
            type="button"
            className="icon-button"
            onClick={() => setIsSidebarOpen(true)}
            aria-label="Show history"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3" y="5" width="18" height="14" rx="3" fill="none" />
              <line x1="9" y1="5" x2="9" y2="19" />
            </svg>
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={handleNewChat}
            aria-label="New chat"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="8" fill="none" />
              <line x1="12" y1="8.5" x2="12" y2="15.5" />
              <line x1="8.5" y1="12" x2="15.5" y2="12" />
            </svg>
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={() => {
              setIsSidebarOpen(true);
              window.setTimeout(() => searchRef.current?.focus(), 0);
            }}
            aria-label="Search chats"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="11" cy="11" r="6" fill="none" />
              <line x1="15.5" y1="15.5" x2="20" y2="20" />
            </svg>
          </button>
        </div>
      </aside>

      <section className="fake-chat">
        <header className="fake-chat__header chat-topbar">
          <div className="fake-chat__actions">
            {!isSidebarOpen ? (
              <button
                type="button"
                className="icon-button icon-button--ghost"
                onClick={() => setIsSidebarOpen(true)}
                aria-label="Show history"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <rect x="3" y="5" width="18" height="14" rx="3" fill="none" />
                  <line x1="9" y1="5" x2="9" y2="19" />
                </svg>
              </button>
            ) : null}
          </div>
          <div className="chat-topbar__title">
            <span className="chat-topbar__badge">Chat</span>
            <span className="chat-topbar__name">Academic Assistant</span>
          </div>
        </header>

        {!hasUserMessages ? (
          <div className="chat-empty">
            <h1 className="chat-empty__title">Задайте вопрос</h1>
            <div className="chat-composer chat-composer--center" role="form" aria-label="Chat composer">
              {profileError ? <p className="error chat-composer__error">{profileError}</p> : null}
              <div className="chat-composer__bar">
                <textarea
                  className="chat-composer__textarea"
                  placeholder="Спросите Academic Assistant..."
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
                Academic Question Bot может допускать ошибки. Проверяйте важную информацию.
              </p>
            </div>
            <div className="chat-suggestions" aria-label="Quick actions">
              {QUICK_ACTIONS.map((item) => (
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
                  placeholder="Спросите Academic Assistant..."
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
                Academic Question Bot может допускать ошибки. Проверяйте важную информацию.
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
