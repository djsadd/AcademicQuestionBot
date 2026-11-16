import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { apiClient, authStorage } from "../../api/client";
import { getChatHistory, getPublicChatHistory, streamChatMessage, streamPublicAdmissionMessage } from "../../api/chat";
import type { ChatRequestPayload } from "../../types";
import { Icon, type IconName } from "../ui/Icon";
import { Logo } from "../ui/Logo";
import { ThemeToggle } from "../ui/ThemeToggle";
import { Composer, type ComposerHandle } from "./Composer";
import { MessageItem } from "./MessageItem";
import {
  applyStageEvent,
  buildChatAnalyticsMetadata,
  buildChatTitle,
  buildRequestHistory,
  buildStorageKey,
  createId,
  createInitialChat,
  createSessionId,
  getContactType,
  getPublicSessionIdFromUrl,
  getStoredPublicContact,
  groupChatsByDate,
  isDefaultTitle,
  isValidContact,
  loadChatState,
  mapHistorySession,
  normalizeChatState,
  saveChatState,
  saveStoredPublicContact,
  type ChatHistoryState,
  type ChatMessage,
  type ChatMode,
  type StageState,
} from "./chatUtils";

type Suggestion = { title: string; prompt: string; icon: IconName };

const VARIANTS: Record<ChatMode, {
  title: string;
  subtitle: string;
  greeting: string;
  intro: string;
  placeholder: string;
  footnote: string;
  context: { university: string; program: string; year: number; itp: string };
  language: string;
  channel: string;
  legacyIntro: string;
  suggestions: Suggestion[];
}> = {
  private: {
    title: "Академический ассистент",
    subtitle: "Учёба, регламенты, календарь, доступ",
    greeting: "Чем могу помочь?",
    intro: "Отвечаю по регламентам и документам TAU, подсказываю даты академического календаря и помогаю с доступом к Platonus.",
    placeholder: "Спросите об учёбе, регламентах или расписании…",
    footnote: "ИИ может ошибаться. Важные решения сверяйте с деканатом.",
    context: { university: "TAU", program: "ComputerScience", year: 2, itp: "ITP-2024" },
    language: "ru",
    channel: "web",
    legacyIntro: "Ask your question about TAU and ITP-2024.",
    suggestions: [
      { title: "Когда сессия?", prompt: "Когда у меня сессия и какие даты экзаменов?", icon: "calendar" },
      { title: "Пересдача и GPA", prompt: "Как работает пересдача и как она влияет на GPA?", icon: "chart" },
      { title: "Справка с места учёбы", prompt: "Как получить справку с места учёбы?", icon: "file" },
      { title: "Не могу войти", prompt: "Я забыл пароль от Platonus. Что делать?", icon: "key" },
    ],
  },
  publicAdmission: {
    title: "Приёмная комиссия TAU",
    subtitle: "Программы, стоимость, документы, гранты",
    greeting: "Поступление в TAU",
    intro: "Спросите о программах, стоимости обучения, проходных баллах, документах или грантах — отвечу по официальным данным приёмной комиссии.",
    placeholder: "Например: сколько стоит обучение на IT?",
    footnote: "Ответы основаны на данных приёмной комиссии TAU. Для важных решений уточняйте информацию.",
    context: { university: "TAU", program: "admission", year: 0, itp: "admissions-public" },
    language: "auto",
    channel: "public_web",
    legacyIntro: "Спросите про поступление в TAU: программы, стоимость, документы, проходные баллы или контакты приемной комиссии.",
    suggestions: [
      { title: "Стоимость обучения", prompt: "Сколько стоит обучение в TAU?", icon: "wallet" },
      { title: "Документы", prompt: "Какие документы нужны для поступления на бакалавриат?", icon: "file" },
      { title: "Проходные баллы", prompt: "Какие проходные баллы ЕНТ на IT-программы?", icon: "chart" },
      { title: "Гранты и скидки", prompt: "Какие есть гранты и скидки для поступающих?", icon: "cap" },
    ],
  },
};

type AuthProfile = {
  telegram_id: number;
  person_id?: string | null;
  platonus_auth?: boolean;
  role?: string | null;
  fullname?: string | null;
  statusName?: string | null;
  email?: string | null;
};

const initials = (name?: string | null) =>
  (name ?? "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("") || "Я";

export function ChatWorkspace({ mode = "private", isAdmin = false }: { mode?: ChatMode; isAdmin?: boolean }) {
  const config = VARIANTS[mode];
  const isPublic = mode === "publicAdmission";
  const navigate = useNavigate();
  const location = useLocation();
  const publicSessionId = isPublic ? getPublicSessionIdFromUrl() : null;

  const [profile, setProfile] = useState<AuthProfile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [storageKey, setStorageKey] = useState(() => buildStorageKey(mode, publicSessionId));
  const [chatState, setChatState] = useState<ChatHistoryState>(() => {
    const stored = loadChatState(buildStorageKey(mode, publicSessionId));
    return stored ? normalizeChatState(stored, config.legacyIntro) : { activeChatId: null, chats: [] };
  });
  const [input, setInput] = useState(() => {
    const state = location.state as { prefill?: unknown } | null;
    return typeof state?.prefill === "string" ? state.prefill.slice(0, 4000) : "";
  });
  const [search, setSearch] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [contact, setContact] = useState(() => (isPublic ? getStoredPublicContact() : ""));
  const [contactDraft, setContactDraft] = useState(contact);
  const [contactError, setContactError] = useState<string | null>(null);
  const [editingContact, setEditingContact] = useState(() => isPublic && !getStoredPublicContact());

  const composerRef = useRef<ComposerHandle | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);
  const draftSessionIdRef = useRef<string>(publicSessionId ?? createSessionId());
  const userMenuRef = useRef<HTMLDivElement | null>(null);

  const activeChat = useMemo(
    () => chatState.chats.find((chat) => chat.id === chatState.activeChatId) ?? null,
    [chatState],
  );
  const messages = activeChat?.messages ?? [];
  const lastMessage = messages[messages.length - 1];

  const filteredGroups = useMemo(() => {
    const query = search.trim().toLowerCase();
    const sorted = [...chatState.chats].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
    const filtered = query
      ? sorted.filter((chat) => chat.title.toLowerCase().includes(query) || chat.messages.some((m) => m.content.toLowerCase().includes(query)))
      : sorted;
    return groupChatsByDate(filtered);
  }, [chatState.chats, search]);

  /* ----------------------------------------------------------- effects */
  useEffect(() => {
    document.title = isPublic ? "Приёмная комиссия · Academiq" : "Чат · Academiq";
  }, [isPublic]);

  useEffect(() => {
    if (isPublic) return;
    let active = true;
    apiClient
      .get<{ user: AuthProfile }>("/auth/me")
      .then((response) => active && setProfile(response.user))
      .catch((error) => active && setProfileError(error instanceof Error ? error.message : "Не удалось загрузить профиль."));
    return () => {
      active = false;
    };
  }, [isPublic]);

  useEffect(() => {
    if (!isPublic && profile?.telegram_id) setStorageKey(buildStorageKey(mode, profile.telegram_id));
  }, [isPublic, mode, profile?.telegram_id]);

  // Re-hydrate when the storage key changes (guest → signed-in user).
  useEffect(() => {
    const stored = loadChatState(storageKey);
    if (stored) {
      setChatState(normalizeChatState(stored, config.legacyIntro));
      return;
    }
    const guestKey = buildStorageKey(mode, null);
    if (storageKey !== guestKey) {
      const guest = loadChatState(guestKey);
      if (guest) {
        setChatState(normalizeChatState(guest, config.legacyIntro));
        return;
      }
    }
    setChatState({ activeChatId: null, chats: [] });
  }, [config.legacyIntro, mode, storageKey]);

  useEffect(() => {
    saveChatState(storageKey, chatState);
  }, [chatState, storageKey]);

  // Server-side history is the source of truth for signed-in users.
  useEffect(() => {
    if (isPublic || !profile?.telegram_id) return;
    let active = true;
    getChatHistory()
      .then((response) => {
        if (!active || !response.sessions.length) return;
        const sessions = response.sessions.map(mapHistorySession);
        setChatState((prev) => {
          const serverIds = new Set(sessions.map((s) => s.sessionId));
          const localOnly = prev.chats.filter((chat) => !serverIds.has(chat.sessionId) && chat.messages.length);
          const chats = [...localOnly, ...sessions];
          return normalizeChatState({ activeChatId: prev.activeChatId ?? chats[0]?.id ?? null, chats });
        });
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [isPublic, profile?.telegram_id]);

  useEffect(() => {
    if (!isPublic || !publicSessionId) return;
    let active = true;
    getPublicChatHistory(publicSessionId)
      .then((response) => {
        if (!active || !response.session) return;
        const session = mapHistorySession(response.session);
        draftSessionIdRef.current = response.session.session_id;
        setChatState({ activeChatId: session.id, chats: [session] });
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [isPublic, publicSessionId]);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    if (!userMenuOpen) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !userMenuRef.current?.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", close);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("keydown", close);
    };
  }, [userMenuOpen]);

  // Follow the stream only while the user is at the bottom of the conversation.
  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return;
    if (!messages.length) {
      element.scrollTop = 0;
      return;
    }
    if (stickToBottomRef.current) element.scrollTop = element.scrollHeight;
  }, [messages.length, lastMessage?.content, lastMessage?.stages?.length]);

  const handleScroll = () => {
    const element = scrollRef.current;
    if (!element) return;
    stickToBottomRef.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
  };

  /* ----------------------------------------------------------- actions */
  const updateMessage = useCallback((chatId: string, messageId: string, patch: Partial<ChatMessage> | ((m: ChatMessage) => Partial<ChatMessage>)) => {
    setChatState((prev) => ({
      ...prev,
      chats: prev.chats.map((chat) =>
        chat.id !== chatId
          ? chat
          : {
              ...chat,
              messages: chat.messages.map((message) =>
                message.id === messageId ? { ...message, ...(typeof patch === "function" ? patch(message) : patch) } : message,
              ),
            },
      ),
    }));
  }, []);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  }, []);

  const handleNewChat = () => {
    stopStreaming();
    setChatState((prev) => ({ ...prev, activeChatId: null }));
    draftSessionIdRef.current = createSessionId();
    setInput("");
    setSidebarOpen(false);
    composerRef.current?.focus();
  };

  const handleSelectChat = (chatId: string) => {
    stopStreaming();
    setChatState((prev) => ({ ...prev, activeChatId: chatId }));
    setSidebarOpen(false);
    stickToBottomRef.current = true;
  };

  const saveContact = () => {
    const value = contactDraft.trim();
    if (!isValidContact(value)) {
      setContactError("Укажите email или номер телефона WhatsApp.");
      return false;
    }
    setContact(value);
    saveStoredPublicContact(value);
    setContactError(null);
    setEditingContact(false);
    return true;
  };

  const sendMessage = (text: string, baseMessages?: ChatMessage[]) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;
    if (isPublic && !contact && !saveContact()) return;
    if (!isPublic && !profile?.telegram_id) {
      setProfileError("Профиль не загружен. Обновите страницу или войдите снова.");
      return;
    }

    const now = new Date().toISOString();
    const userMessage: ChatMessage = { id: createId("user"), role: "user", content: trimmed, createdAt: now };
    const botMessageId = createId("bot");
    const botMessage: ChatMessage = { id: botMessageId, role: "bot", content: "", status: "pending", stages: [], createdAt: now };
    const chat = activeChat ?? { ...createInitialChat(), sessionId: draftSessionIdRef.current };
    const chatId = chat.id;
    const previous = baseMessages ?? chat.messages;
    const history = buildRequestHistory(previous);

    setChatState((prev) => {
      const exists = prev.chats.some((item) => item.id === chatId);
      const nextChat = {
        ...chat,
        title: isDefaultTitle(chat.title) ? buildChatTitle(trimmed) : chat.title,
        updatedAt: now,
        messages: [...previous, userMessage, botMessage],
      };
      return {
        activeChatId: chatId,
        chats: exists ? prev.chats.map((item) => (item.id === chatId ? nextChat : item)) : [nextChat, ...prev.chats],
      };
    });
    setInput("");
    stickToBottomRef.current = true;
    if (!activeChat) draftSessionIdRef.current = createSessionId();

    const contactValue = contact.trim();
    const payload: ChatRequestPayload = {
      user_id: isPublic ? undefined : profile?.telegram_id,
      telegram_id: isPublic ? undefined : profile?.telegram_id,
      person_id: isPublic ? undefined : profile?.person_id ?? undefined,
      uuid: isPublic ? chat.sessionId : undefined,
      message: trimmed,
      language: config.language,
      context: isPublic
        ? {
            ...config.context,
            contact: {
              value: contactValue,
              type: getContactType(contactValue),
              preferred_channel: getContactType(contactValue) === "email" ? "email" : "whatsapp",
            },
          }
        : config.context,
      metadata: buildChatAnalyticsMetadata({
        profile,
        isPublicAdmission: isPublic,
        mode,
        message: trimmed,
        sessionId: chat.sessionId,
        channel: config.channel,
        context: config.context,
        historyLength: history.length,
        publicContact: contactValue,
      }),
      history,
    };

    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);

    let streamed = "";
    let pending = "";
    let flushTimer: number | null = null;
    let stages: StageState[] = [];
    const flush = () => {
      flushTimer = null;
      if (!pending) return;
      streamed += pending;
      pending = "";
      updateMessage(chatId, botMessageId, { content: streamed });
    };

    const request = isPublic ? streamPublicAdmissionMessage : streamChatMessage;
    request(
      payload,
      {
        onDelta: (delta) => {
          pending += delta;
          if (!flushTimer) flushTimer = window.setTimeout(flush, 32);
        },
        onStage: (event) => {
          stages = applyStageEvent(stages, event);
          updateMessage(chatId, botMessageId, { stages });
        },
      },
      controller.signal,
    )
      .then((response) => {
        if (flushTimer) window.clearTimeout(flushTimer);
        streamed += pending;
        const result = response.result;
        updateMessage(chatId, botMessageId, {
          content: result.final_answer || streamed || "Ассистент не вернул ответ.",
          status: undefined,
          details: result,
          stages: stages.map((stage) => (stage.status === "running" ? { ...stage, status: "done" as const } : stage)),
        });
      })
      .catch((error: unknown) => {
        if (flushTimer) window.clearTimeout(flushTimer);
        if (error instanceof Error && error.name === "AbortError") {
          updateMessage(chatId, botMessageId, (message) => ({
            status: message.content || streamed ? undefined : "error",
            content: message.content || streamed || "Ответ остановлен.",
          }));
          return;
        }
        updateMessage(chatId, botMessageId, {
          status: "error",
          content: error instanceof Error ? error.message : "Не удалось получить ответ.",
        });
      })
      .finally(() => {
        if (abortRef.current === controller) abortRef.current = null;
        setIsStreaming(false);
      });
  };

  const handleRetry = (botMessageId: string) => {
    if (!activeChat) return;
    const index = activeChat.messages.findIndex((message) => message.id === botMessageId);
    const userMessage = activeChat.messages[index - 1];
    if (index < 1 || userMessage?.role !== "user") return;
    sendMessage(userMessage.content, activeChat.messages.slice(0, index - 1));
  };

  const handleLogout = async () => {
    const refreshToken = authStorage.getRefreshToken();
    try {
      if (refreshToken) await apiClient.post("/auth/logout", JSON.stringify({ refresh_token: refreshToken }));
    } catch {
      // Tokens are cleared locally anyway.
    } finally {
      authStorage.clearTokens();
      navigate("/telegram-login", { replace: true });
    }
  };

  const displayName = profile?.fullname?.trim() || profile?.email?.trim() || "Пользователь";
  const userInitials = isPublic ? "Вы" : initials(profile?.fullname);

  /* ------------------------------------------------------------ render */
  return (
    <div className={`chat-app${sidebarOpen ? " chat-app--sidebar-open" : ""}`}>
      <aside className="chat-sidebar" aria-label="История диалогов">
        <div className="chat-sidebar__head">
          <Logo to={isPublic ? "/" : "/chat"} subtitle={isPublic ? "Приёмная комиссия" : "TAU Assistant"} />
          <button type="button" className="icon-button chat-sidebar__close" onClick={() => setSidebarOpen(false)} aria-label="Закрыть">
            <Icon name="x" />
          </button>
        </div>

        <button type="button" className="chat-sidebar__new" onClick={handleNewChat}>
          <Icon name="plus" size={16} />
          <span>Новый диалог</span>
        </button>

        <label className="chat-sidebar__search">
          <Icon name="search" size={16} />
          <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Поиск по диалогам" />
        </label>

        <nav className="chat-sidebar__list">
          {filteredGroups.length ? (
            filteredGroups.map((group) => (
              <div key={group.label} className="chat-sidebar__group">
                <span className="chat-sidebar__group-title">{group.label}</span>
                {group.chats.map((chat) => (
                  <button
                    key={chat.id}
                    type="button"
                    className={`chat-sidebar__item${chat.id === activeChat?.id ? " is-active" : ""}`}
                    onClick={() => handleSelectChat(chat.id)}
                    title={chat.title}
                  >
                    <Icon name="chat" size={15} />
                    <span>{chat.title}</span>
                  </button>
                ))}
              </div>
            ))
          ) : (
            <p className="chat-sidebar__empty">{search ? "Ничего не найдено" : "Здесь появятся ваши диалоги"}</p>
          )}
        </nav>

        <div className="chat-sidebar__foot">
          {isPublic ? (
            <Link to="/telegram-login" className="chat-sidebar__cta">
              <Icon name="user" size={16} />
              <span>
                <strong>Студент TAU?</strong>
                <small>Войдите для персональных ответов</small>
              </span>
            </Link>
          ) : (
            <div className="user-menu" ref={userMenuRef}>
              {userMenuOpen ? (
                <div className="user-menu__popover" role="menu">
                  <Link to="/profile" className="user-menu__item" role="menuitem">
                    <Icon name="user" size={16} /> Профиль
                  </Link>
                  {isAdmin ? (
                    <Link to="/chat-analytics" className="user-menu__item" role="menuitem">
                      <Icon name="chart" size={16} /> Панель управления
                    </Link>
                  ) : null}
                  <button type="button" className="user-menu__item user-menu__item--danger" role="menuitem" onClick={handleLogout}>
                    <Icon name="logout" size={16} /> Выйти
                  </button>
                </div>
              ) : null}
              <button type="button" className="user-menu__trigger" onClick={() => setUserMenuOpen((value) => !value)} aria-haspopup="menu" aria-expanded={userMenuOpen}>
                <span className="user-menu__avatar">{userInitials}</span>
                <span className="user-menu__text">
                  <span className="user-menu__name">{displayName}</span>
                  <span className="user-menu__meta">{profile?.statusName || profile?.role || "Аккаунт TAU"}</span>
                </span>
                <Icon name="chevronDown" size={16} />
              </button>
            </div>
          )}
        </div>
      </aside>
      <div className="chat-backdrop" onClick={() => setSidebarOpen(false)} aria-hidden="true" />

      <section className="chat-main">
        <header className="chat-topbar">
          <button type="button" className="icon-button chat-topbar__menu" onClick={() => setSidebarOpen(true)} aria-label="Открыть историю">
            <Icon name="menu" />
          </button>
          <div className="chat-topbar__title">
            <strong>{activeChat && !isDefaultTitle(activeChat.title) ? activeChat.title : config.title}</strong>
            <span className="chat-topbar__subtitle">
              <span className="status-dot" /> {config.subtitle}
            </span>
          </div>
          <div className="chat-topbar__actions">
            <button type="button" className="icon-button" onClick={handleNewChat} aria-label="Новый диалог" title="Новый диалог">
              <Icon name="plus" />
            </button>
            <ThemeToggle />
          </div>
        </header>

        <div className="chat-scroll" ref={scrollRef} onScroll={handleScroll}>
          {messages.length ? (
            <div className="chat-thread">
              {messages.map((message) => (
                <MessageItem
                  key={message.id}
                  message={message}
                  userInitials={userInitials}
                  onRetry={message.status === "error" ? () => handleRetry(message.id) : undefined}
                />
              ))}
            </div>
          ) : (
            <div className="chat-welcome">
              <div className="chat-welcome__badge">
                <Icon name="sparkles" size={14} /> ИИ-ассистент TAU
              </div>
              <h1>{config.greeting}</h1>
              <p className="muted">{config.intro}</p>
              <div className="chat-suggestions">
                {config.suggestions.map((item) => (
                  <button key={item.title} type="button" className="chat-suggestion" onClick={() => sendMessage(item.prompt)} disabled={isStreaming}>
                    <span className="chat-suggestion__icon"><Icon name={item.icon} size={18} /></span>
                    <span className="chat-suggestion__text">
                      <strong>{item.title}</strong>
                      <span>{item.prompt}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="chat-bottom">
          {profileError ? (
            <div className="chat-alert" role="alert">
              <Icon name="alert" size={16} /> {profileError}
            </div>
          ) : null}
          {isPublic ? (
            editingContact ? (
              <form
                className="contact-card"
                onSubmit={(event) => {
                  event.preventDefault();
                  saveContact();
                }}
              >
                <div className="contact-card__text">
                  <strong>Как с вами связаться?</strong>
                  <span>Приёмная комиссия сможет ответить вам лично, если понадобится.</span>
                </div>
                <div className="contact-card__row">
                  <input
                    type="text"
                    inputMode="email"
                    autoComplete="email tel"
                    value={contactDraft}
                    onChange={(event) => setContactDraft(event.target.value)}
                    placeholder="Email или WhatsApp"
                    aria-invalid={Boolean(contactError)}
                    aria-label="Контакт для связи"
                  />
                  <button type="submit" className="primary">Сохранить</button>
                </div>
                {contactError ? <span className="contact-card__error">{contactError}</span> : null}
              </form>
            ) : (
              <div className="contact-chip">
                <Icon name="phone" size={14} />
                <span>Связь: {contact}</span>
                <button type="button" onClick={() => setEditingContact(true)}>Изменить</button>
              </div>
            )
          ) : null}
          <Composer
            ref={composerRef}
            value={input}
            onChange={setInput}
            onSubmit={() => sendMessage(input)}
            onStop={stopStreaming}
            isStreaming={isStreaming}
            placeholder={config.placeholder}
            footnote={config.footnote}
          />
        </div>
      </section>
    </div>
  );
}
