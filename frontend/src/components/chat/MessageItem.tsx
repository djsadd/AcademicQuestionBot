import { memo, useMemo, useState } from "react";
import { Icon } from "../ui/Icon";
import { LogoMark } from "../ui/Logo";
import { AgentProgress, AgentSummary } from "./AgentProgress";
import { formatMessageContent, stripHtml, type ChatMessage } from "./chatUtils";

type Props = {
  message: ChatMessage;
  userInitials: string;
  onRetry?: () => void;
};

function Sources({ message }: { message: ChatMessage }) {
  const sources = useMemo(() => {
    const seen = new Set<string>();
    const list: { label: string; title: string }[] = [];
    for (const raw of message.details?.citations ?? []) {
      const cite = raw as Record<string, unknown>;
      const name = String(cite.title ?? cite.file_name ?? "").replace(/^[0-9a-f]{32}_/, "").trim();
      if (!name || name.endsWith(".json")) continue;
      const page = cite.page ? `, стр. ${cite.page}` : "";
      const key = `${name}${page}`;
      if (seen.has(key)) continue;
      seen.add(key);
      list.push({ label: key, title: [name, cite.section].filter(Boolean).join(" — ") });
    }
    return list.slice(0, 4);
  }, [message.details?.citations]);
  if (!sources.length) return null;
  return (
    <div className="message-sources" aria-label="Источники">
      <span className="message-sources__label">Источники</span>
      {sources.map((source) => (
        <span key={source.label} className="message-source" title={source.title}>
          <Icon name="file" size={13} />
          <span>{source.label}</span>
        </span>
      ))}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard can be blocked (http, iframe); fail silently.
    }
  };
  return (
    <button type="button" className="message-action" onClick={copy} aria-label="Скопировать ответ" title="Скопировать">
      <Icon name={copied ? "check" : "copy"} size={15} />
      <span>{copied ? "Скопировано" : "Копировать"}</span>
    </button>
  );
}

function MessageItemBase({ message, userInitials, onRetry }: Props) {
  const isUser = message.role === "user";
  const isPending = message.status === "pending";
  const isError = message.status === "error";
  const html = useMemo(() => (isUser ? "" : formatMessageContent(message.content)), [isUser, message.content]);

  if (isUser) {
    return (
      <article className="message message--user">
        <div className="message__bubble">{message.content}</div>
        <span className="message__avatar message__avatar--user" aria-hidden="true">{userInitials}</span>
      </article>
    );
  }

  return (
    <article className={`message message--bot${isError ? " message--error" : ""}`}>
      <span className="message__avatar" aria-hidden="true">
        <LogoMark size={30} />
      </span>
      <div className="message__body">
        {isPending && !message.content ? <AgentProgress stages={message.stages ?? []} /> : null}
        {isError ? (
          <div className="message__error" role="alert">
            <Icon name="alert" size={16} />
            <span>{message.content || "Не удалось получить ответ."}</span>
          </div>
        ) : message.content ? (
          <div className={`message__content prose${isPending ? " is-streaming" : ""}`} dangerouslySetInnerHTML={{ __html: html }} />
        ) : null}
        {!isPending && !isError ? <Sources message={message} /> : null}
        {!isPending ? (
          <div className="message__actions">
            {isError && onRetry ? (
              <button type="button" className="message-action" onClick={onRetry}>
                <Icon name="refresh" size={15} />
                <span>Повторить</span>
              </button>
            ) : null}
            {!isError && message.content ? <CopyButton text={stripHtml(message.content)} /> : null}
            {!isError && message.stages?.length ? (
              <AgentSummary stages={message.stages} totalMs={message.details?.timings_ms?.total} />
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}

export const MessageItem = memo(MessageItemBase);
