import { useMemo, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  fetchChatAnalyticsSessionEvents,
  fetchChatAnalyticsSessions,
  fetchChatAnalyticsSummary,
} from "../api/admin";
import type {
  ChatAnalyticsEvent,
  ChatAnalyticsSession,
  ChatAnalyticsSessionListResponse,
} from "../types";
import { formatDate } from "../utils/format";

const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
const AUTH_MODE_OPTIONS = [
  { value: "all", label: "Все чаты" },
  { value: "anonymous", label: "Анонимные" },
  { value: "authenticated", label: "Пользователи" },
] as const;

function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="analytics-json-block">
      {JSON.stringify(value ?? null, null, 2)}
    </pre>
  );
}

type HtmlViewMode = "rendered" | "html" | "text";

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
      const attrValue = attr.value.trim().toLowerCase();
      if (name.startsWith("on")) {
        node.removeAttribute(attr.name);
      }
      if ((name === "href" || name === "src") && attrValue.startsWith("javascript:")) {
        node.removeAttribute(attr.name);
      }
    });
  });
  return document.body.innerHTML;
};

const stripHtml = (value: string) => {
  if (!value) return "";
  if (typeof window === "undefined") {
    return value
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/(p|div|li|h[1-6]|tr|section|article)>/gi, "\n")
      .replace(/<[^>]+>/g, "")
      .trim();
  }

  const parser = new DOMParser();
  const document = parser.parseFromString(value, "text/html");
  document.querySelectorAll("br").forEach((node) => node.replaceWith("\n"));
  document.querySelectorAll("p, div, li, h1, h2, h3, h4, h5, h6, tr, section, article").forEach((node) => {
    node.append(document.createTextNode("\n"));
  });
  return (document.body.textContent ?? "").replace(/\n{3,}/g, "\n\n").trim();
};

const looksLikeHtml = (value: string) => /<\/?[a-z][\s\S]*>/i.test(value);

function HtmlContentBlock({
  value,
  title,
}: {
  value: string | null | undefined;
  title: string;
}) {
  const [mode, setMode] = useState<HtmlViewMode>("rendered");

  const content = value?.trim() ?? "";
  const hasHtml = looksLikeHtml(content);

  if (!content) {
    return <p className="analytics-answer-block">-</p>;
  }

  if (!hasHtml) {
    return <p className="analytics-answer-block">{content}</p>;
  }

  const sanitized = sanitizeHtml(content);
  const plainText = stripHtml(content);

  return (
    <div className="analytics-html-viewer">
      <div className="analytics-html-viewer__toolbar" role="tablist" aria-label={`${title} format`}>
        <button
          type="button"
          className={`analytics-html-viewer__tab${mode === "rendered" ? " active" : ""}`}
          onClick={() => setMode("rendered")}
        >
          Preview
        </button>
        <button
          type="button"
          className={`analytics-html-viewer__tab${mode === "html" ? " active" : ""}`}
          onClick={() => setMode("html")}
        >
          HTML
        </button>
        <button
          type="button"
          className={`analytics-html-viewer__tab${mode === "text" ? " active" : ""}`}
          onClick={() => setMode("text")}
        >
          Text
        </button>
      </div>

      {mode === "rendered" ? (
        <div
          className="analytics-answer-block analytics-answer-block--html"
          dangerouslySetInnerHTML={{ __html: sanitized }}
        />
      ) : mode === "html" ? (
        <pre className="analytics-answer-block analytics-answer-block--code">
          <code>{content}</code>
        </pre>
      ) : (
        <pre className="analytics-answer-block analytics-answer-block--text">
          {plainText || stripHtml(sanitized) || "-"}
        </pre>
      )}
    </div>
  );
}

function SessionQuestions({
  session,
  onOpen,
}: {
  session: ChatAnalyticsSession;
  onOpen: (session: ChatAnalyticsSession, question?: string) => void;
}) {
  if (!session.questions.length) {
    return <span className="muted">Вопросов не найдено</span>;
  }

  return (
    <div className="analytics-question-list">
      {session.questions.slice(0, 5).map((item, index) => (
        <button
          key={`${item.created_at}-${index}`}
          type="button"
          className="analytics-question-item analytics-question-item--button"
          onClick={() => onOpen(session, item.query)}
        >
          <strong>{item.query}</strong>
          <small>{formatDate(item.created_at)}</small>
        </button>
      ))}
    </div>
  );
}

function findMatchingEvent(events: ChatAnalyticsEvent[], selectedQuery: string | null) {
  if (!selectedQuery) return events[0] ?? null;
  return events.find((item) => item.query === selectedQuery) ?? events[0] ?? null;
}

function getAnonymousUuid(
  session: Pick<ChatAnalyticsSession, "auth_mode" | "request_uuid" | "session_id" | "session_key">,
) {
  if (session.auth_mode !== "anonymous") return null;
  return session.request_uuid || null;
}

function EventLogModal({
  session,
  selectedQuery,
  onClose,
}: {
  session: ChatAnalyticsSession;
  selectedQuery: string | null;
  onClose: () => void;
}) {
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const eventsQuery = useQuery({
    queryKey: ["chat-analytics-session-events", session.session_key],
    queryFn: () => fetchChatAnalyticsSessionEvents(session.session_key),
  });

  const events = eventsQuery.data?.items ?? [];
  const activeEvent =
    events.find((item) => item.id === selectedEventId)
    ?? findMatchingEvent(events, selectedQuery);
  const incomingRequest = activeEvent ? {
    uuid: activeEvent.request_uuid ?? activeEvent.request_payload?.uuid ?? null,
    session_id: activeEvent.session_id,
    channel: activeEvent.channel,
    auth_mode: activeEvent.auth_mode,
    metadata_request: activeEvent.metadata?.request ?? null,
    metadata_context_snapshot: activeEvent.metadata?.context_snapshot ?? null,
    request_payload: activeEvent.request_payload ?? {},
  } : null;

  return (
    <div className="chat-properties-modal__overlay" onClick={onClose} role="presentation">
      <div
        className="chat-properties-modal__panel analytics-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Chat event details"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="chat-properties-modal__header">
          <div>
            <h3>Детали сессии</h3>
            <p className="muted">Session ID: {session.session_id}</p>
            {getAnonymousUuid(session) ? <p className="muted">UUID: {getAnonymousUuid(session)}</p> : null}
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close">
            x
          </button>
        </div>

        {eventsQuery.isLoading ? (
          <p>Загрузка логов события...</p>
        ) : eventsQuery.isError ? (
          <p className="error">Не удалось загрузить детали сессии.</p>
        ) : !events.length || !activeEvent ? (
          <p className="muted">Логи по этой сессии пока не найдены.</p>
        ) : (
          <div className="analytics-modal__layout">
            <aside className="analytics-event-list">
              {events.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`analytics-event-list__item${item.id === activeEvent.id ? " active" : ""}`}
                  onClick={() => setSelectedEventId(item.id)}
                >
                  <strong>{item.query || "Без текста запроса"}</strong>
                  <small>{item.created_at ? formatDate(item.created_at) : "-"}</small>
                </button>
              ))}
            </aside>

            <div className="analytics-event-detail">
              <div className="analytics-detail-section">
                <span className="eyebrow">Question</span>
                <HtmlContentBlock value={activeEvent.query} title="Question" />
              </div>

              <div className="analytics-detail-section">
                <span className="eyebrow">AI Answer</span>
                <HtmlContentBlock value={activeEvent.response} title="AI Answer" />
              </div>

              <div className="analytics-detail-grid">
                <div className="analytics-detail-card">
                  <span>LLM model</span>
                  <strong>{activeEvent.llm_model || "-"}</strong>
                </div>
                <div className="analytics-detail-card">
                  <span>LLM used</span>
                  <strong>{String(activeEvent.llm_used ?? false)}</strong>
                </div>
                <div className="analytics-detail-card">
                  <span>Channel</span>
                  <strong>{activeEvent.channel || "-"}</strong>
                </div>
                <div className="analytics-detail-card">
                  <span>Created</span>
                  <strong>{activeEvent.created_at ? formatDate(activeEvent.created_at) : "-"}</strong>
                </div>
              </div>

              <div className="analytics-detail-section analytics-detail-section--wide">
                <span className="eyebrow">Incoming request JSON</span>
                <JsonBlock value={incomingRequest} />
              </div>

              <div className="analytics-detail-section">
                <span className="eyebrow">Intents</span>
                <JsonBlock value={activeEvent.intents} />
              </div>

              <div className="analytics-detail-section">
                <span className="eyebrow">Agents / Plan</span>
                <JsonBlock value={activeEvent.agents} />
              </div>

              <div className="analytics-detail-section">
                <span className="eyebrow">Trace / Tools / Context</span>
                <JsonBlock value={activeEvent.trace} />
              </div>

              <div className="analytics-detail-section">
                <span className="eyebrow">Metadata</span>
                <JsonBlock value={activeEvent.metadata} />
              </div>

              <div className="analytics-detail-section">
                <span className="eyebrow">Request payload</span>
                <JsonBlock value={activeEvent.request_payload} />
              </div>

              <div className="analytics-detail-section">
                <span className="eyebrow">Response payload</span>
                <JsonBlock value={activeEvent.response_payload} />
              </div>

              {activeEvent.llm_error ? (
                <div className="analytics-detail-section">
                  <span className="eyebrow">LLM error</span>
                  <p className="error">{activeEvent.llm_error}</p>
                </div>
              ) : null}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ChatAnalyticsLogsPanel({
  sessionItems,
  page,
  perPage,
  authMode,
  searchInput,
  setAuthMode,
  setPerPage,
  setSearchInput,
  setSearch,
  setPage,
  sessionsQuery,
  openSessionDetails,
}: {
  sessionItems: ChatAnalyticsSession[];
  page: number;
  perPage: number;
  authMode: string;
  searchInput: string;
  setAuthMode: (value: string) => void;
  setPerPage: (value: number) => void;
  setSearchInput: (value: string) => void;
  setSearch: (value: string) => void;
  setPage: (value: number | ((current: number) => number)) => void;
  sessionsQuery: UseQueryResult<ChatAnalyticsSessionListResponse, Error>;
  openSessionDetails: (session: ChatAnalyticsSession, question?: string) => void;
}) {
  return (
    <div className="panel">
      <div className="admin-toolbar">
        <div className="admin-toolbar__summary">
          <strong>Логи сессий: {sessionsQuery.data?.total ?? 0}</strong>
          <span className="muted">
            Страница {sessionsQuery.data?.page ?? page}
            {sessionsQuery.data?.pages ? ` из ${sessionsQuery.data.pages}` : ""}
          </span>
        </div>

        <div className="analytics-toolbar-group">
          <label className="admin-toolbar__control">
            <span>Тип чата</span>
            <select
              value={authMode}
              onChange={(event) => {
                setAuthMode(event.target.value);
                setPage(1);
              }}
            >
              {AUTH_MODE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="admin-toolbar__control">
            <span>На странице</span>
            <select
              value={perPage}
              onChange={(event) => {
                setPerPage(Number(event.target.value));
                setPage(1);
              }}
            >
              {PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <form
            className="analytics-search"
            onSubmit={(event) => {
              event.preventDefault();
              setSearch(searchInput.trim());
              setPage(1);
            }}
          >
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Поиск по запросу, имени, email, Telegram ID"
            />
            <button type="submit" className="ghost">Найти</button>
          </form>
        </div>
      </div>

      {sessionsQuery.isLoading ? (
        <p>Загрузка логов чатов...</p>
      ) : sessionsQuery.isError ? (
        <p className="error">Не удалось загрузить логи чатов.</p>
      ) : sessionItems.length === 0 ? (
        <p className="muted">Подходящих логов нет.</p>
      ) : (
        <>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Сессия</th>
                  <th>Тип</th>
                  <th>Пользователь</th>
                  <th>Вопросы пользователя</th>
                  <th>Активность</th>
                </tr>
              </thead>
              <tbody>
                {sessionItems.map((item) => (
                  <tr key={item.session_key}>
                    <td>
                      <div className="doc-name">
                        <strong>{item.session_id}</strong>
                        {getAnonymousUuid(item) ? <small>UUID: {getAnonymousUuid(item)}</small> : null}
                        <small>Канал: {item.channel || "-"}</small>
                        <small>Событий: {item.event_count}</small>
                        <button
                          type="button"
                          className="ghost analytics-open-button"
                          onClick={() => openSessionDetails(item)}
                        >
                          Открыть логи
                        </button>
                      </div>
                    </td>
                    <td>
                      <span className={`status-pill ${item.auth_mode === "anonymous" ? "status-pending" : "status-success"}`}>
                        {item.auth_mode === "anonymous" ? "Анонимный" : "Пользователь"}
                      </span>
                    </td>
                    <td>
                      <div className="doc-name">
                        <strong>{item.full_name || item.email || (item.auth_mode === "anonymous" ? "Публичный анонимный пользователь" : "Авторизованный пользователь")}</strong>
                        <small>Telegram ID: {item.telegram_id ?? "-"}</small>
                        <small>Person ID: {item.person_id ?? "-"}</small>
                      </div>
                    </td>
                    <td>
                      <SessionQuestions session={item} onOpen={openSessionDetails} />
                    </td>
                    <td>
                      <div className="doc-name">
                        <small>Начало: {item.started_at ? formatDate(item.started_at) : "-"}</small>
                        <small>Последнее событие: {item.updated_at ? formatDate(item.updated_at) : "-"}</small>
                        <small>Последний запрос: {item.last_query || "-"}</small>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <button
              className="ghost"
              onClick={() => setPage((current) => Math.max(current - 1, 1))}
              disabled={page <= 1}
            >
              Назад
            </button>
            <span className="pagination__status">
              Страница {sessionsQuery.data?.page ?? page}
              {sessionsQuery.data?.pages ? ` из ${sessionsQuery.data.pages}` : ""}
            </span>
            <button
              className="ghost"
              onClick={() => setPage((current) => current + 1)}
              disabled={sessionsQuery.data?.pages ? page >= sessionsQuery.data.pages : sessionItems.length < perPage}
            >
              Вперед
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export function ChatAnalytics() {
  const location = useLocation();
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState<number>(20);
  const [authMode, setAuthMode] = useState("all");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [selectedSession, setSelectedSession] = useState<ChatAnalyticsSession | null>(null);
  const [selectedQuery, setSelectedQuery] = useState<string | null>(null);

  const summaryQuery = useQuery({
    queryKey: ["chat-analytics-summary"],
    queryFn: () => fetchChatAnalyticsSummary(),
  });

  const sessionsQuery = useQuery({
    queryKey: ["chat-analytics-sessions", page, perPage, authMode, search],
    queryFn: () => fetchChatAnalyticsSessions(page, perPage, authMode, search),
    placeholderData: (previousData) => previousData,
  });

  const summaryCards = useMemo(() => {
    const summary = summaryQuery.data;
    if (!summary) return [];
    return [
      { label: "Всего событий", value: summary.total_events },
      { label: "Всего сессий", value: summary.total_sessions },
      { label: "Анонимные сессии", value: summary.anonymous_sessions },
      { label: "Сессии пользователей", value: summary.authenticated_sessions },
      { label: "Уникальные пользователи", value: summary.unique_users },
      { label: "Последний лог", value: summary.last_event_at ? formatDate(summary.last_event_at) : "Нет" },
    ];
  }, [summaryQuery.data]);

  const sessionItems = sessionsQuery.data?.items ?? [];

  const openSessionDetails = (session: ChatAnalyticsSession, question?: string) => {
    setSelectedSession(session);
    setSelectedQuery(question ?? null);
  };

  if (location.pathname === "/chat-analytics" || location.pathname === "/chat-analytics/") {
    return <Navigate to="/chat-analytics/logs" replace />;
  }

  return (
    <section className="feature-section">
      <div className="feature-section__header">
        <div>
          <p className="eyebrow">Chat Analytics</p>
          <h2>Аналитика и логи чатов</h2>
          <p className="muted">
            Здесь остались только логи и детализация сессий. Пользователи вынесены в отдельный раздел меню.
          </p>
        </div>
        <span className="feature-section__status">
          {summaryQuery.data?.total_events ?? 0} logs
        </span>
      </div>

      <div className="analytics-summary-grid">
        {summaryQuery.isLoading
          ? <p>Загрузка общей статистики...</p>
          : summaryCards.map((card) => (
            <article key={card.label} className="analytics-summary-card">
              <span>{card.label}</span>
              <strong>{card.value}</strong>
            </article>
          ))}
      </div>

      <ChatAnalyticsLogsPanel
        sessionItems={sessionItems}
        page={page}
        perPage={perPage}
        authMode={authMode}
        searchInput={searchInput}
        setAuthMode={setAuthMode}
        setPerPage={setPerPage}
        setSearchInput={setSearchInput}
        setSearch={setSearch}
        setPage={setPage}
        sessionsQuery={sessionsQuery}
        openSessionDetails={openSessionDetails}
      />

      {selectedSession ? (
        <EventLogModal
          session={selectedSession}
          selectedQuery={selectedQuery}
          onClose={() => {
            setSelectedSession(null);
            setSelectedQuery(null);
          }}
        />
      ) : null}
    </section>
  );
}
