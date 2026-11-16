import { useState } from "react";
import { Icon } from "../ui/Icon";
import { formatDuration, STAGE_LABELS, type StageState } from "./chatUtils";

/** Live list of pipeline steps while the answer is being prepared. */
export function AgentProgress({ stages }: { stages: StageState[] }) {
  const visible = stages.filter((item) => STAGE_LABELS[item.stage]);
  if (!visible.length) {
    return (
      <div className="agent-progress" role="status" aria-live="polite">
        <div className="agent-progress__step is-running">
          <span className="agent-progress__dot" />
          <span>Подключаюсь к ассистенту…</span>
        </div>
      </div>
    );
  }
  return (
    <ol className="agent-progress" role="status" aria-live="polite">
      {visible.map((item) => (
        <li key={item.stage} className={`agent-progress__step is-${item.status}`}>
          <span className="agent-progress__dot">{item.status === "done" ? <Icon name="check" size={11} strokeWidth={3} /> : null}</span>
          <span>{STAGE_LABELS[item.stage]}</span>
          {item.status === "done" && item.durationMs !== undefined ? (
            <span className="agent-progress__time">{formatDuration(item.durationMs)}</span>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

/** Collapsed "how this answer was produced" summary under a finished answer. */
export function AgentSummary({ stages, totalMs }: { stages: StageState[]; totalMs?: number }) {
  const [open, setOpen] = useState(false);
  const visible = stages.filter((item) => STAGE_LABELS[item.stage] && item.status !== "running");
  if (!visible.length) return null;
  return (
    <div className="agent-summary">
      <button type="button" className="agent-summary__toggle" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <Icon name="sparkles" size={14} />
        <span>
          {visible.length} {visible.length === 1 ? "шаг" : visible.length < 5 ? "шага" : "шагов"}
          {totalMs ? ` · ${formatDuration(totalMs)}` : ""}
        </span>
        <Icon name="chevronDown" size={14} className={open ? "is-flipped" : undefined} />
      </button>
      {open ? <AgentProgress stages={visible} /> : null}
    </div>
  );
}
