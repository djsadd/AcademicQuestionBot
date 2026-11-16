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

export function Pagination({
  page,
  pages,
  onChange,
  hasNext,
  perPage,
  perPageOptions,
  onPerPageChange,
  total,
}: {
  page: number;
  pages?: number;
  onChange: (page: number) => void;
  hasNext?: boolean;
  perPage?: number;
  perPageOptions?: readonly number[];
  onPerPageChange?: (value: number) => void;
  total?: number;
}) {
  const canNext = pages ? page < pages : Boolean(hasNext);
  return (
    <div className="pager">
      <span className="pager__info muted">
        {total !== undefined ? `Всего: ${total.toLocaleString("ru-RU")}` : null}
        {perPage && perPageOptions && onPerPageChange ? (
          <select value={perPage} onChange={(event) => onPerPageChange(Number(event.target.value))} aria-label="Строк на странице">
            {perPageOptions.map((option) => (
              <option key={option} value={option}>{option} на странице</option>
            ))}
          </select>
        ) : null}
      </span>
      <div className="pager__controls">
        <button type="button" className="icon-button" onClick={() => onChange(page - 1)} disabled={page <= 1} aria-label="Предыдущая страница">
          <Icon name="chevronRight" size={16} style={{ transform: "rotate(180deg)" }} />
        </button>
        <span className="pager__page">{pages ? `${page} из ${pages}` : page}</span>
        <button type="button" className="icon-button" onClick={() => onChange(page + 1)} disabled={!canNext} aria-label="Следующая страница">
          <Icon name="chevronRight" size={16} />
        </button>
      </div>
    </div>
  );
}

export function LoadingRows({ rows = 3, height = 52 }: { rows?: number; height?: number }) {
  return (
    <div className="skeleton-list">
      {Array.from({ length: rows }, (_, index) => <div key={index} className="skeleton" style={{ height }} />)}
    </div>
  );
}

export function Drawer({ title, subtitle, onClose, children, width = 980 }: { title: ReactNode; subtitle?: ReactNode; onClose: () => void; children: ReactNode; width?: number }) {
  return (
    <div className="drawer" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside className="drawer__panel" role="dialog" aria-modal="true" style={{ maxWidth: width }} onKeyDown={(event) => event.key === "Escape" && onClose()}>
        <header className="drawer__head">
          <div className="drawer__title">
            <h3>{title}</h3>
            {subtitle ? <span className="muted">{subtitle}</span> : null}
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Закрыть" autoFocus>
            <Icon name="x" />
          </button>
        </header>
        <div className="drawer__body">{children}</div>
      </aside>
    </div>
  );
}

export function JsonDetails({ title, value, open = false }: { title: string; value: unknown; open?: boolean }) {
  return (
    <details className="json-details" open={open}>
      <summary>{title}</summary>
      <pre className="code-block">{JSON.stringify(value ?? null, null, 2)}</pre>
    </details>
  );
}
