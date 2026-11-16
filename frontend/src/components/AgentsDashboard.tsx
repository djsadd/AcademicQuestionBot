import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAgentsOverview } from "../api/admin";
import type { AgentOverviewItem } from "../types";
import { formatNumber, formatRelative } from "../utils/format";
import { Callout, EmptyState, LoadingRows, PageHeader, StatCard } from "./ui/Admin";
import { Icon, type IconName } from "./ui/Icon";

const WINDOW_OPTIONS = [7, 30, 90] as const;

const STATE_META: Record<string, { label: string; className: string }> = {
  healthy: { label: "Работает", className: "status-success" },
  degraded: { label: "Есть ошибки", className: "status-failed" },
  idle: { label: "Не используется", className: "status-idle" },
};

const AGENT_ICONS: Record<string, IconName> = {
  intent: "sparkles",
  tutor: "book",
  policy: "file",
  admission: "cap",
  dean: "calendar",
  validator: "shield",
};

function AgentCard({ item }: { item: AgentOverviewItem }) {
  const state = STATE_META[item.state] ?? { label: item.state, className: "status-pending" };
  const rate = Math.max(0, Math.min(100, item.success_rate || 0));
  return (
    <article className="agent-card">
      <header className="agent-card__head">
        <span className="agent-card__icon"><Icon name={AGENT_ICONS[item.key] ?? "cpu"} size={20} /></span>
        <div className="agent-card__title">
          <strong>{item.label}</strong>
          <span className="muted">{item.description || item.name}</span>
        </div>
        <span className={`status-pill ${state.className}`}>{state.label}</span>
      </header>

      <div className="agent-card__metrics">
        <div><span>Запуски</span><strong>{formatNumber(item.executions)}</strong></div>
        <div><span>Сессии</span><strong>{formatNumber(item.sessions)}</strong></div>
        <div><span>Ошибки</span><strong className={item.error_count ? "text-danger" : undefined}>{formatNumber(item.error_count)}</strong></div>
        <div><span>Прямые ответы</span><strong>{formatNumber(item.direct_response_count)}</strong></div>
      </div>

      <div className="agent-card__rate">
        <div className="agent-card__rate-label">
          <span>Успешность</span>
          <strong>{item.executions ? `${rate}%` : "—"}</strong>
        </div>
        <div className="progress"><span style={{ width: `${item.executions ? rate : 0}%` }} /></div>
      </div>

      <footer className="agent-card__foot">
        <span>
          <Icon name="users" size={13} /> {formatNumber(item.authenticated_count)} авториз. · {formatNumber(item.anonymous_count)} аноним.
        </span>
        <span><Icon name="clock" size={13} /> {item.last_used_at ? formatRelative(item.last_used_at) : "не запускался"}</span>
      </footer>
      {item.channel_breakdown.length ? (
        <div className="chip-row">
          {item.channel_breakdown.map((entry) => (
            <span key={entry.channel} className="tag tag--muted">{entry.channel}: {formatNumber(entry.count)}</span>
          ))}
        </div>
      ) : null}
      {item.last_error ? <div className="agent-card__error" title={item.last_error}>{item.last_error}</div> : null}
    </article>
  );
}

export function AgentsDashboard() {
  const [windowDays, setWindowDays] = useState<number>(30);
  const agentsQuery = useQuery({
    queryKey: ["agents-overview", windowDays],
    queryFn: () => fetchAgentsOverview(windowDays),
    refetchInterval: 60_000,
  });
  const summary = agentsQuery.data?.summary;
  const items = agentsQuery.data?.items ?? [];

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Мониторинг"
        title="ИИ-агенты"
        description="Нагрузка и надёжность каждого агента пайплайна по журналу выполнения."
        actions={
          <div className="segmented" role="group" aria-label="Период">
            {WINDOW_OPTIONS.map((option) => (
              <button key={option} type="button" className={windowDays === option ? "is-active" : undefined} onClick={() => setWindowDays(option)}>
                {option} дн.
              </button>
            ))}
          </div>
        }
      />

      <div className="stat-grid">
        <StatCard label="Всего агентов" icon="cpu" value={formatNumber(summary?.total_agents)} />
        <StatCard label="Активны за период" icon="activity" tone="brand" value={formatNumber(summary?.active_agents)} />
        <StatCard label="Работают без ошибок" icon="check" tone="success" value={formatNumber(summary?.healthy_agents)} />
        <StatCard label="С ошибками" icon="alert" tone={summary?.degraded_agents ? "danger" : undefined} value={formatNumber(summary?.degraded_agents)} />
      </div>

      {agentsQuery.isLoading ? (
        <LoadingRows rows={3} height={180} />
      ) : agentsQuery.isError ? (
        <Callout tone="danger" title="Не удалось загрузить метрики агентов">{(agentsQuery.error as Error).message}</Callout>
      ) : !items.length ? (
        <EmptyState icon="cpu" title="Нет данных" text="Метрики появятся после первых диалогов." />
      ) : (
        <div className="agent-grid">
          {items.map((item) => <AgentCard key={item.key} item={item} />)}
        </div>
      )}
    </div>
  );
}
