import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchChatAnalyticsSessions,
  fetchChatAnalyticsSummary,
  fetchChatAnalyticsUsers,
} from "../api/admin";
import type { ChatAnalyticsQuestion } from "../types";
import { formatDate } from "../utils/format";

const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
const AUTH_MODE_OPTIONS = [
  { value: "all", label: "Все чаты" },
  { value: "anonymous", label: "Анонимные" },
  { value: "authenticated", label: "Пользователи" },
] as const;

function renderQuestions(questions: ChatAnalyticsQuestion[], emptyLabel: string) {
  if (!questions.length) {
    return <span className="muted">{emptyLabel}</span>;
  }
  return (
    <div className="analytics-question-list">
      {questions.slice(0, 5).map((item, index) => (
        <div key={`${item.created_at}-${index}`} className="analytics-question-item">
          <strong>{item.query}</strong>
          <small>{formatDate(item.created_at)}</small>
        </div>
      ))}
    </div>
  );
}

export function ChatAnalytics() {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState<number>(20);
  const [authMode, setAuthMode] = useState("all");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  const summaryQuery = useQuery({
    queryKey: ["chat-analytics-summary"],
    queryFn: () => fetchChatAnalyticsSummary(),
  });

  const usersQuery = useQuery({
    queryKey: ["chat-analytics-users"],
    queryFn: () => fetchChatAnalyticsUsers(100),
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
  const userItems = usersQuery.data?.items ?? [];

  return (
    <section className="feature-section">
      <div className="feature-section__header">
        <div>
          <p className="eyebrow">Chat Analytics</p>
          <h2>Аналитика и логи чатов</h2>
          <p className="muted">
            Публичные анонимные диалоги и чаты авторизованных пользователей собираются в одной админ-панели.
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

      <div className="panel">
        <div className="feature-section__header">
          <div>
            <p className="eyebrow">Users</p>
            <h3>Список пользователей</h3>
          </div>
          <span className="muted">{userItems.length} записей</span>
        </div>

        {usersQuery.isLoading ? (
          <p>Загрузка пользователей...</p>
        ) : usersQuery.isError ? (
          <p className="error">Не удалось загрузить список пользователей.</p>
        ) : userItems.length === 0 ? (
          <p className="muted">Авторизованных пользователей пока нет.</p>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Пользователь</th>
                  <th>Идентификаторы</th>
                  <th>Активность</th>
                  <th>Последние вопросы</th>
                </tr>
              </thead>
              <tbody>
                {userItems.map((item) => (
                  <tr key={item.user_key}>
                    <td>
                      <div className="doc-name">
                        <strong>{item.full_name || item.email || `User ${item.telegram_id ?? item.person_id ?? "-"}`}</strong>
                        <small>{item.email || "Email не указан"}</small>
                        <small>Роль: {item.role || "-"}</small>
                      </div>
                    </td>
                    <td>
                      <div className="doc-name">
                        <small>Telegram ID: {item.telegram_id ?? "-"}</small>
                        <small>Person ID: {item.person_id ?? "-"}</small>
                      </div>
                    </td>
                    <td>
                      <div className="doc-name">
                        <small>События: {item.event_count}</small>
                        <small>Сессии: {item.session_count}</small>
                        <small>Последняя активность: {item.last_seen ? formatDate(item.last_seen) : "-"}</small>
                      </div>
                    </td>
                    <td>{renderQuestions(item.recent_queries, "Запросов пока нет")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

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
                          <small>Канал: {item.channel || "-"}</small>
                          <small>Событий: {item.event_count}</small>
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
                      <td>{renderQuestions(item.questions, "Вопросов не найдено")}</td>
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
    </section>
  );
}
