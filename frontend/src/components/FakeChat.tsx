import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { getChatHistory, sendChatMessage } from "../api/chat";
import type { ChatHistorySession, ChatRequestPayload, ChatResult } from "../types";

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

const stripHtml = (value: string) => value.replace(/<[^>]*>/g, "").trim();

const formatMessageContent = (value: string) => {
  if (/<\/?[a-z][\s\S]*>/i.test(value)) {
    return sanitizeHtml(value);
  }
  return escapeHtml(value).replace(/\n/g, "<br />");
};

const buildChatTitle = (message: string) => {
  const trimmed = message.replace(/\s+/g, " ").trim();
  if (!trimmed) return DEFAULT_CHAT_TITLE;
  return trimmed.length > 48 ? `${trimmed.slice(0, 48)}...` : trimmed;
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
  if (!chats.length) {
    const chat = createInitialChat();
    return { activeChatId: chat.id, chats: [chat] };
  }
  const activeChatId =
    state.activeChatId && chats.some((chat) => chat.id === state.activeChatId)
      ? state.activeChatId
      : chats[0].id;
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

export function FakeChat() {
  const [inputValue, setInputValue] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [profile, setProfile] = useState<AuthProfile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [storageKey, setStorageKey] = useState(() => buildStorageKey(null));
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [highlightedChatId, setHighlightedChatId] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const highlightTimeoutRef = useRef<number | null>(null);
  const [chatState, setChatState] = useState<ChatHistoryState>(() => {
    if (typeof window === "undefined") {
      const chat = createInitialChat();
      return { activeChatId: chat.id, chats: [chat] };
    }
    const stored = loadChatState(buildStorageKey(null));
    if (stored) return stored;
    const chat = createInitialChat();
    return { activeChatId: chat.id, chats: [chat] };
  });
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const activeChat = useMemo(() => {
    const active =
      chatState.chats.find((chat) => chat.id === chatState.activeChatId)
      ?? chatState.chats[0];
    return active ?? null;
  }, [chatState]);

  const sortedChats = useMemo(() => {
    return [...chatState.chats].sort(
      (first, second) =>
        new Date(second.updatedAt).getTime() - new Date(first.updatedAt).getTime()
    );
  }, [chatState.chats]);

  const requestMeta = useMemo(() => {
    return {
      language: DEFAULT_PROFILE.language,
      channel: "web",
      session: activeChat?.sessionId ?? createSessionId(),
      university: DEFAULT_PROFILE.context.university,
      program: DEFAULT_PROFILE.context.program,
      itp: DEFAULT_PROFILE.context.itp,
    };
  }, [activeChat?.sessionId]);

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
    const chat = createInitialChat();
    const nextState = { activeChatId: chat.id, chats: [chat] };
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
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeChat?.messages.length]);

  const chatMutation = useMutation<ChatResult, Error, string>({
    mutationFn: async (message: string) => {
      const payload: ChatRequestPayload = {
        user_id: profile?.telegram_id ?? 0,
        telegram_id: profile?.telegram_id,
        person_id: profile?.person_id ?? undefined,
        message,
        language: DEFAULT_PROFILE.language,
        context: DEFAULT_PROFILE.context,
        metadata: {
          channel: "web",
          session_id: requestMeta.session,
        },
      };
      const response = await sendChatMessage(payload);
      return response.result;
    },
  });

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

  const handleNewChat = () => {
    const chat = createInitialChat();
    setChatState((prev) => ({
      activeChatId: chat.id,
      chats: [chat, ...prev.chats],
    }));
    setHighlightedChatId(chat.id);
    if (highlightTimeoutRef.current) {
      window.clearTimeout(highlightTimeoutRef.current);
    }
    highlightTimeoutRef.current = window.setTimeout(() => {
      setHighlightedChatId(null);
    }, 700);
    setExpandedId(null);
    setInputValue("");
  };

  const handleSelectChat = (chatId: string) => {
    setChatState((prev) => ({ ...prev, activeChatId: chatId }));
    setExpandedId(null);
  };

  const handleSend = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
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
      content: BOT_PLACEHOLDER,
      status: "pending",
    };

    const activeChatId = activeChat?.id ?? createInitialChat().id;
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

    chatMutation.mutate(trimmed, {
      onSuccess: (result) => {
        replaceMessage(activeChatId, botMessageId, {
          content: result.final_answer || "No answer from the agent.",
          status: undefined,
          details: result,
        });
      },
      onError: (error) => {
        replaceMessage(activeChatId, botMessageId, {
          content: error instanceof Error ? error.message : "Request failed.",
          status: "error",
        });
      },
    });
  };

  return (
    <section className={`chat-shell${isSidebarOpen ? "" : " chat-shell--collapsed"}`}>
      <aside className="chat-sidebar" aria-hidden={!isSidebarOpen}>
        <div className="chat-sidebar__content">
          <div className="chat-sidebar__header">
            <div className="chat-sidebar__actions">
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
                onClick={() => setIsSidebarOpen(false)}
                aria-label="Collapse history"
              >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <rect x="3" y="5" width="18" height="14" rx="3" fill="none" />
                <line x1="9" y1="5" x2="9" y2="19" />
              </svg>
            </button>
            </div>
          </div>
          <div className="chat-sidebar__list">
            {sortedChats.map((chat) => {
              const lastMessage = chat.messages[chat.messages.length - 1];
              const preview = lastMessage?.content
                ? stripHtml(lastMessage.content).slice(0, 64)
                : "No messages yet.";
              return (
                <button
                  type="button"
                  key={chat.id}
                  className={`chat-list-item${
                    chat.id === activeChat?.id ? " active" : ""
                  }${chat.id === highlightedChatId ? " chat-list-item--new" : ""}`}
                  onClick={() => handleSelectChat(chat.id)}
                >
                  <span className="chat-list-item__title">{chat.title}</span>
                  <span className="chat-list-item__preview">
                    {preview || "No messages yet."}
                  </span>
                  <span className="chat-list-item__meta">{formatChatDate(chat.updatedAt)}</span>
                </button>
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
            onClick={() => inputRef.current?.focus()}
            aria-label="Focus input"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="11" cy="11" r="6" fill="none" />
              <line x1="15.5" y1="15.5" x2="20" y2="20" />
            </svg>
          </button>
        </div>
      </aside>

      <section className="fake-chat">
        <header className="fake-chat__header">
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
        </header>

        <div
          className={`chat-window${
            activeChat?.id === highlightedChatId ? " chat-window--new" : ""
          }`}
        >
          <div className="chat-messages">
            {(activeChat?.messages ?? []).map((message) => (
              <div
                key={message.id}
                className={`chat-bubble ${message.role === "user" ? "user" : "bot"}${
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
                <span className="bubble-label">
                  {message.role === "user" ? "User" : "Bot"}
                </span>
                <div
                  className="chat-bubble__content"
                  dangerouslySetInnerHTML={{
                    __html: formatMessageContent(message.content),
                  }}
                />
                {message.role === "bot" && message.details ? (
                  <div
                    className={`chat-bubble__details ${
                      expandedId === message.id ? "open" : ""
                    }`}
                  >
                    <span className="chat-bubble__details-label">Details JSON</span>
                    <pre>{JSON.stringify(message.details, null, 2)}</pre>
                  </div>
                ) : null}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        <div className="chat-input-area">
          {profileError ? <p className="error">{profileError}</p> : null}
          <textarea
            placeholder="Type your question..."
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
            className="primary"
            onClick={handleSend}
            disabled={!inputValue.trim() || chatMutation.isPending}
          >
            Send
          </button>
        </div>
      </section>
    </section>
  );
}
