import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

export function PageHeader({ title, description, actions, eyebrow }: { title: string; description?: ReactNode; actions?: ReactNode; eyebrow?: string }) {
  return (
    <header className="page-header">
      <div className="page-header__text">
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <h2>{title}</h2>
        {description ? <p className="muted">{description}</p> : null}
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </header>
  );
}

export function StatCard({ label, value, hint, icon, tone }: { label: string; value: ReactNode; hint?: ReactNode; icon?: IconName; tone?: "success" | "warning" | "danger" | "brand" }) {
  return (
    <article className={`stat-card${tone ? ` stat-card--${tone}` : ""}`}>
      <div className="stat-card__top">
        <span className="stat-card__label">{label}</span>
        {icon ? <span className="stat-card__icon"><Icon name={icon} size={16} /></span> : null}
      </div>
      <strong className="stat-card__value">{value}</strong>
      {hint ? <span className="stat-card__hint">{hint}</span> : null}
    </article>
  );
}

const STATUS_LABELS: Record<string, string> = {
  queued: "В очереди",
  processing: "Индексация",
  ingested: "Готов",
  failed: "Ошибка",
  pending: "Ожидание",
  success: "Готово",
  failure: "Ошибка",
};

export function StatusBadge({ status }: { status?: string | null }) {
  const key = (status ?? "pending").toLowerCase();
  return (
    <span className={`status-pill status-${key}${key === "processing" || key === "queued" ? " is-animated" : ""}`}>
      {STATUS_LABELS[key] ?? status}
    </span>
  );
}

export function EmptyState({ icon = "file", title, text, action }: { icon?: IconName; title: string; text?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <span className="empty-state__icon"><Icon name={icon} size={22} /></span>
      <strong>{title}</strong>
      {text ? <p className="muted">{text}</p> : null}
      {action}
    </div>
  );
}

export function Callout({ tone = "warning", title, children, action }: { tone?: "warning" | "danger" | "info" | "success"; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={`callout callout--${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <Icon name={tone === "success" ? "check" : "alert"} size={18} />
      <div className="callout__body">
        <strong>{title}</strong>
        {children ? <div className="callout__text">{children}</div> : null}
      </div>
      {action ? <div className="callout__action">{action}</div> : null}
    </div>
  );
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (value: T) => void; items: { value: T; label: string; count?: number; icon?: IconName }[] }) {
  return (
    <div className="tabs" role="tablist">
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          role="tab"
          aria-selected={value === item.value}
          className={`tabs__item${value === item.value ? " is-active" : ""}`}
          onClick={() => onChange(item.value)}
        >
          {item.icon ? <Icon name={item.icon} size={16} /> : null}
          {item.label}
          {item.count !== undefined ? <span className="tabs__count">{item.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
