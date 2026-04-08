import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAgentsOverview } from "../api/admin";
import type { AgentOverviewItem } from "../types";
import { formatDate } from "../utils/format";

const WINDOW_OPTIONS = [7, 30, 90] as const;

function getStateClassName(state: string) {
  if (state === "healthy") return "status-success";
  if (state === "degraded") return "status-failed";
  return "status-pending";
}

function formatChannels(item: AgentOverviewItem) {
  if (!item.channel_breakdown.length) return "Нет данных";
  return item.channel_breakdown.map((entry) => `${entry.channel}: ${entry.count}`).join(", ");
}

export function AgentsDashboard() {
  const [windowDays, setWindowDays] = useState<number>(30);

  const agentsQuery = useQuery({
    queryKey: ["agents-overview", windowDays],
    queryFn: () => fetchAgentsOverview(windowDays),
  });

  const summary = agentsQuery.data?.summary;
  const items = agentsQuery.data?.items ?? [];

  return (
    <section className="feature-section">
      <div className="feature-section__header">
        <div>
          <p className="eyebrow">Agents</p>
          <h2>Агенты, метрики и состояние</h2>
          <p className="muted">Сводка по всем агентам из оркестратора на основе логов исполнения.</p>
        </div>
        <span className="feature-section__status">
          {summary?.active_agents ?? 0} active
        </span>
      </div>

      <div className="admin-toolbar">
        <div className="admin-toolbar__summary">
          <strong>Все агенты: {summary?.total_agents ?? 0}</strong>
          <span className="muted">
            Healthy: {summary?.healthy_agents ?? 0} · Degraded: {summary?.degraded_agents ?? 0} · Idle: {summary?.idle_agents ?? 0}
          </span>
        </div>

        <label className="admin-toolbar__control">
          <span>Окно аналитики</span>
          <select value={windowDays} onChange={(event) => setWindowDays(Number(event.target.value))}>
            {WINDOW_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option} дней
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="analytics-summary-grid">
        <article className="analytics-summary-card">
          <span>Активные агенты</span>
          <strong>{summary?.active_agents ?? 0}</strong>
        </article>
        <article className="analytics-summary-card">
          <span>Healthy</span>
          <strong>{summary?.healthy_agents ?? 0}</strong>
        </article>
        <article className="analytics-summary-card">
          <span>Degraded</span>
          <strong>{summary?.degraded_agents ?? 0}</strong>
        </article>
        <article className="analytics-summary-card">
          <span>Idle</span>
          <strong>{summary?.idle_agents ?? 0}</strong>
        </article>
      </div>

      {agentsQuery.isLoading ? (
        <p>Загрузка метрик агентов...</p>
      ) : agentsQuery.isError ? (
        <p className="error">Не удалось загрузить метрики агентов.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Агент</th>
                <th>Состояние</th>
                <th>Метрики</th>
                <th>Трафик</th>
                <th>Последняя активность</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.key}>
                  <td>
                    <div className="doc-name">
                      <strong>{item.label}</strong>
                      <small>{item.name}</small>
                      <small>{item.description || "Описание не задано"}</small>
                      <small>Тип: {item.kind}</small>
                    </div>
                  </td>
                  <td>
                    <div className="doc-name">
                      <span className={`status-pill ${getStateClassName(item.state)}`}>
                        {item.state}
                      </span>
                      <small>Last status: {item.last_status || "-"}</small>
                      <small>{item.last_error ? `Ошибка: ${item.last_error}` : "Ошибок не зафиксировано"}</small>
                    </div>
                  </td>
                  <td>
                    <div className="doc-name">
                      <small>Запуски: {item.executions}</small>
                      <small>Сессии: {item.sessions}</small>
                      <small>Успешно: {item.success_count}</small>
                      <small>Ошибки: {item.error_count}</small>
                      <small>Success rate: {item.success_rate}%</small>
                    </div>
                  </td>
                  <td>
                    <div className="doc-name">
                      <small>Authenticated: {item.authenticated_count}</small>
                      <small>Anonymous: {item.anonymous_count}</small>
                      <small>Direct responses: {item.direct_response_count}</small>
                      <small>Channels: {formatChannels(item)}</small>
                    </div>
                  </td>
                  <td>
                    <div className="doc-name">
                      <small>{item.last_used_at ? formatDate(item.last_used_at) : "Нет запусков"}</small>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
