import { useQuery } from "@tanstack/react-query";
import { fetchChatAnalyticsUsers } from "../api/admin";
import type { ChatAnalyticsQuestion, ChatAnalyticsUser } from "../types";
import { formatDate } from "../utils/format";

function UserQuestions({ questions }: { questions: ChatAnalyticsQuestion[] }) {
  if (!questions.length) {
    return <span className="muted">Запросов пока нет</span>;
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

function ChatUsersPanel({ userItems }: { userItems: ChatAnalyticsUser[] }) {
  return (
    <div className="panel">
      <div className="feature-section__header">
        <div>
          <p className="eyebrow">Users</p>
          <h3>Пользователи чата</h3>
          <p className="muted">Отдельный список авторизованных пользователей и их последней активности.</p>
        </div>
        <span className="muted">{userItems.length} записей</span>
      </div>

      {userItems.length === 0 ? (
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
                  <td><UserQuestions questions={item.recent_queries} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function ChatUsers() {
  const usersQuery = useQuery({
    queryKey: ["chat-analytics-users"],
    queryFn: () => fetchChatAnalyticsUsers(100),
  });

  return (
    <section className="feature-section">
      <div className="feature-section__header">
        <div>
          <p className="eyebrow">Users</p>
          <h2>Пользователи</h2>
          <p className="muted">Отдельный раздел после логов чата с пользователями и их историей запросов.</p>
        </div>
        <span className="feature-section__status">
          {usersQuery.data?.items.length ?? 0} users
        </span>
      </div>

      {usersQuery.isLoading ? (
        <p>Загрузка пользователей...</p>
      ) : usersQuery.isError ? (
        <p className="error">Не удалось загрузить список пользователей.</p>
      ) : (
        <ChatUsersPanel userItems={usersQuery.data?.items ?? []} />
      )}
    </section>
  );
}
