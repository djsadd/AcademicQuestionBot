import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAdmissionContactLeads, fetchChatAnalyticsSessionEvents, fetchChatAnalyticsSessions, fetchChatAnalyticsSummary } from "../api/admin";
import type { AdmissionContactLead, ChatAnalyticsEvent, ChatAnalyticsSession } from "../types";
import { formatDate, formatNumber, formatRelative } from "../utils/format";
import { formatMessageContent, STAGE_LABELS } from "./chat/chatUtils";
import { Callout, Drawer, EmptyState, JsonDetails, LoadingRows, PageHeader, Pagination, StatCard, Tabs } from "./ui/Admin";
import { Icon } from "./ui/Icon";

type Tab = "sessions" | "contacts";
const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
const AUTH_MODES = [
  { value: "all", label: "Все" },
  { value: "anonymous", label: "Абитуриенты" },
  { value: "authenticated", label: "Студенты" },
] as const;

const sessionUser = (session: Pick<ChatAnalyticsSession, "full_name" | "email" | "admission_contact" | "auth_mode" | "telegram_id">) =>
  session.full_name || session.email || session.admission_contact || (session.auth_mode === "anonymous" ? "Аноним" : `Пользователь ${session.telegram_id ?? ""}`);

/* ------------------------------------------------------------ details */
type TraceItem = { key?: string; name?: string; description?: string; duration_ms?: number; status?: string; output?: Record<string, unknown> };

function PipelineTrace({ trace }: { trace: unknown[] }) {
  const items = (Array.isArray(trace) ? trace : []) as TraceItem[];
  if (!items.length) return null;
  return (
    <ol className="trace">
      {items.map((item, index) => {
        const failed = item.status === "error" || Boolean(item.output?.error);
        const intents = item.key === "intent" ? (item.output?.intents as string[] | undefined) : undefined;
        const issues = item.key === "validator" ? (item.output?.issues as string[] | undefined) : undefined;
        return (
          <li key={`${item.key}-${index}`} className={`trace__step${failed ? " is-error" : ""}`}>
            <span className="trace__dot">{failed ? <Icon name="x" size={11} strokeWidth={3} /> : <Icon name="check" size={11} strokeWidth={3} />}</span>
            <div className="trace__text">
              <strong>{STAGE_LABELS[item.key ?? ""] ?? item.description ?? item.key}</strong>
              <span className="muted">
                {item.description ?? item.name}
                {intents?.length ? ` · интенты: ${intents.join(", ")}` : ""}
                {issues?.length ? ` · замечания: ${issues.join(", ")}` : ""}
                {failed && item.output?.error ? ` · ${String(item.output.error)}` : ""}
              </span>
            </div>
            {item.duration_ms !== undefined ? <span className="trace__time">{item.duration_ms} мс</span> : null}
          </li>
        );
      })}
    </ol>
  );
}

function EventDetail({ event }: { event: ChatAnalyticsEvent }) {
  const [raw, setRaw] = useState(false);
  const answerHtml = useMemo(() => formatMessageContent(event.response ?? ""), [event.response]);
  return (
    <div className="event-detail">
      <div className="convo">
        <div className="convo__user">{event.query || "—"}</div>
        <div className="convo__bot">
          <div className="convo__bot-head">
            <span className="muted">Ответ ассистента</span>
            <button type="button" className="chip" onClick={() => setRaw((value) => !value)}>{raw ? "Как видит пользователь" : "Исходный текст"}</button>
          </div>
          {raw ? <pre className="code-block">{event.response || "—"}</pre> : <div className="prose" dangerouslySetInnerHTML={{ __html: answerHtml || "—" }} />}
        </div>
      </div>

      <div className="meta-grid">
        <div><span>Модель</span><strong>{event.llm_model || "—"}</strong></div>
        <div><span>LLM</span><strong>{event.llm_used ? "использована" : "без LLM"}</strong></div>
        <div><span>Канал</span><strong>{event.channel || "—"}</strong></div>
        <div><span>Время</span><strong>{formatDate(event.created_at)}</strong></div>
      </div>
      {event.llm_error ? <Callout tone="danger" title="Ошибка LLM">{event.llm_error}</Callout> : null}

      <section className="stack">
        <h4>Как получен ответ</h4>
        <PipelineTrace trace={event.trace} />
      </section>

      <section className="stack">
        <h4>Технические данные</h4>
        <JsonDetails title="Интенты" value={event.intents} />
        <JsonDetails title="План агентов" value={event.agents} />
        <JsonDetails title="Трасса (полная)" value={event.trace} />
        <JsonDetails title="Метаданные" value={event.metadata} />
        <JsonDetails title="Запрос" value={event.request_payload} />
        <JsonDetails title="Ответ API" value={event.response_payload} />
      </section>
    </div>
  );
}

function SessionDrawer({ session, initialQuery, onClose }: { session: ChatAnalyticsSession; initialQuery: string | null; onClose: () => void }) {
  const eventsQuery = useQuery({
    queryKey: ["chat-analytics-session-events", session.session_key],
    queryFn: () => fetchChatAnalyticsSessionEvents(session.session_key),
  });
  const events = useMemo(() => eventsQuery.data?.items ?? [], [eventsQuery.data]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    if (selectedId || !events.length) return;
    setSelectedId((events.find((item) => item.query === initialQuery) ?? events[0]).id);
  }, [events, initialQuery, selectedId]);

  const active = events.find((item) => item.id === selectedId) ?? null;

  return (
    <Drawer
      title={sessionUser(session)}
      subtitle={<>{session.auth_mode === "anonymous" ? "Абитуриент" : "Студент"} · {session.channel ?? "—"} · сессия {session.session_id}</>}
      onClose={onClose}
    >
      {eventsQuery.isLoading ? (
        <LoadingRows rows={4} />
      ) : eventsQuery.isError ? (
        <Callout tone="danger" title="Не удалось загрузить сессию">{(eventsQuery.error as Error).message}</Callout>
      ) : !events.length ? (
        <EmptyState icon="chat" title="В сессии нет сообщений" />
      ) : (
        <div className="session-layout">
          <nav className="session-list" aria-label="Сообщения">
            {events.map((item, index) => (
              <button key={item.id} type="button" className={`session-list__item${item.id === active?.id ? " is-active" : ""}`} onClick={() => setSelectedId(item.id)}>
                <span className="session-list__num">{index + 1}</span>
                <span className="session-list__text">
                  <strong>{item.query || "Без текста"}</strong>
                  <span>{formatDate(item.created_at)}</span>
                </span>
                {item.llm_error ? <Icon name="alert" size={14} className="text-danger" /> : null}
              </button>
            ))}
          </nav>
          {active ? <EventDetail key={active.id} event={active} /> : null}
        </div>
      )}
    </Drawer>
  );
}

/* --------------------------------------------------------------- tabs */
function SessionsTab({ onOpen }: { onOpen: (session: ChatAnalyticsSession, query?: string) => void }) {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState<number>(20);
  const [authMode, setAuthMode] = useState("all");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const query = useQuery({
    queryKey: ["chat-analytics-sessions", page, perPage, authMode, search],
    queryFn: () => fetchChatAnalyticsSessions(page, perPage, authMode, search),
    placeholderData: (previous) => previous,
  });
  const items = query.data?.items ?? [];

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setSearch(searchInput.trim());
    setPage(1);
  };

  return (
    <section className="panel">
      <div className="toolbar">
        <form className="toolbar__search" onSubmit={submit}>
          <Icon name="search" size={16} />
          <input type="search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Вопрос, имя, email, Telegram ID — Enter" />
        </form>
        <div className="segmented" role="group" aria-label="Тип пользователя">
          {AUTH_MODES.map((mode) => (
            <button key={mode.value} type="button" className={authMode === mode.value ? "is-active" : undefined} onClick={() => { setAuthMode(mode.value); setPage(1); }}>
              {mode.label}
            </button>
          ))}
        </div>
      </div>

      {query.isLoading ? (
        <LoadingRows rows={5} height={64} />
      ) : query.isError ? (
        <Callout tone="danger" title="Не удалось загрузить диалоги">{(query.error as Error).message}</Callout>
      ) : !items.length ? (
        <EmptyState icon="chat" title="Диалогов не найдено" text={search ? "Измените запрос или фильтр." : undefined} />
      ) : (
        <>
          <div className="table-wrapper">
            <table className="click-table">
              <thead>
                <tr>
                  <th>Пользователь</th>
                  <th>Последний вопрос</th>
                  <th className="num">Сообщений</th>
                  <th>Активность</th>
                </tr>
              </thead>
              <tbody>
                {items.map((session) => (
                  <tr key={session.session_key} onClick={() => onOpen(session)} tabIndex={0} onKeyDown={(event) => event.key === "Enter" && onOpen(session)}>
                    <td>
                      <div className="person">
                        <span className={`person__avatar${session.auth_mode === "anonymous" ? " person__avatar--muted" : ""}`}>
                          <Icon name={session.auth_mode === "anonymous" ? "cap" : "user"} size={15} />
                        </span>
                        <span className="person__text">
                          <strong>{sessionUser(session)}</strong>
                          <span>{session.auth_mode === "anonymous" ? "Абитуриент" : "Студент"} · {session.channel ?? "—"}</span>
                        </span>
                      </div>
                    </td>
                    <td className="cell-question">
                      <span>{session.last_query || "—"}</span>
                      {session.questions.length > 1 ? (
                        <div className="chip-row">
                          {session.questions.slice(0, 3).map((item, index) => (
                            <button
                              key={`${item.created_at}-${index}`}
                              type="button"
                              className="chip chip--sm"
                              onClick={(event) => { event.stopPropagation(); onOpen(session, item.query); }}
                              title={item.query}
                            >
                              {item.query.length > 40 ? `${item.query.slice(0, 40)}…` : item.query}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </td>
                    <td className="num">{formatNumber(session.event_count)}</td>
                    <td className="nowrap muted">{formatRelative(session.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={query.data?.page ?? page}
            pages={query.data?.pages}
            onChange={setPage}
            hasNext={items.length >= perPage}
            total={query.data?.total}
            perPage={perPage}
            perPageOptions={PAGE_SIZE_OPTIONS}
            onPerPageChange={(value) => { setPerPage(value); setPage(1); }}
          />
        </>
      )}
    </section>
  );
}

function ContactsTab({ contacts, isLoading, error, onOpen }: { contacts: AdmissionContactLead[]; isLoading: boolean; error: Error | null; onOpen: (lead: AdmissionContactLead) => void }) {
  if (isLoading) return <LoadingRows rows={4} height={64} />;
  if (error) return <Callout tone="danger" title="Не удалось загрузить контакты">{error.message}</Callout>;
  if (!contacts.length) return <EmptyState icon="phone" title="Контактов пока нет" text="Абитуриенты оставляют email или WhatsApp перед вопросом в публичном чате." />;
  return (
    <section className="panel">
      <div className="table-wrapper">
        <table className="click-table">
          <thead>
            <tr>
              <th>Контакт</th>
              <th>Последний вопрос</th>
              <th className="num">Сообщений</th>
              <th>Активность</th>
            </tr>
          </thead>
          <tbody>
            {contacts.map((lead) => {
              const isEmail = (lead.contact_type ?? "").includes("email") || lead.contact.includes("@");
              const href = isEmail ? `mailto:${lead.contact}` : `https://wa.me/${lead.contact.replace(/\D/g, "")}`;
              return (
                <tr key={`${lead.contact}-${lead.session_key}`} onClick={() => onOpen(lead)} tabIndex={0}>
                  <td>
                    <div className="person">
                      <span className="person__avatar person__avatar--muted"><Icon name={isEmail ? "external" : "phone"} size={15} /></span>
                      <span className="person__text">
                        <a href={href} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}><strong>{lead.contact}</strong></a>
                        <span>{isEmail ? "Email" : "WhatsApp"} · {lead.channel ?? "—"}</span>
                      </span>
                    </div>
                  </td>
                  <td className="cell-question"><span>{lead.last_query || "—"}</span></td>
                  <td className="num">{formatNumber(lead.event_count)}<div className="muted cell-sub">{lead.session_count} сесс.</div></td>
                  <td className="nowrap muted">{formatRelative(lead.last_seen)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/* --------------------------------------------------------------- page */
export function ChatAnalytics() {
  const [tab, setTab] = useState<Tab>("sessions");
  const [selected, setSelected] = useState<{ session: ChatAnalyticsSession; query: string | null } | null>(null);
  const summaryQuery = useQuery({ queryKey: ["chat-analytics-summary"], queryFn: fetchChatAnalyticsSummary, refetchInterval: 60_000 });
  const contactsQuery = useQuery({ queryKey: ["chat-analytics-admission-contacts"], queryFn: () => fetchAdmissionContactLeads(100) });
  const summary = summaryQuery.data;
  const contacts = contactsQuery.data?.items ?? [];

  const openContact = (lead: AdmissionContactLead) =>
    setSelected({
      query: lead.last_query ?? null,
      session: {
        session_key: lead.session_key,
        session_id: lead.session_id,
        request_uuid: null,
        channel: lead.channel,
        telegram_id: null,
        person_id: null,
        full_name: null,
        email: null,
        admission_contact: lead.contact,
        auth_mode: "anonymous",
        event_count: lead.event_count,
        started_at: lead.first_seen,
        updated_at: lead.last_seen,
        last_query: lead.last_query,
        last_response: lead.last_response,
        questions: lead.recent_queries,
      },
    });

  return (
    <div className="stack-lg">
      <PageHeader eyebrow="Мониторинг" title="Диалоги" description="Все разговоры с ассистентом: вопросы, ответы и то, как пайплайн агентов их получил." />

      <div className="stat-grid">
        <StatCard label="Диалогов" icon="chat" value={formatNumber(summary?.total_sessions)} hint={summary?.last_event_at ? `последний ${formatRelative(summary.last_event_at)}` : undefined} />
        <StatCard label="Сообщений" icon="activity" tone="brand" value={formatNumber(summary?.total_events)} />
        <StatCard label="Абитуриенты" icon="cap" value={formatNumber(summary?.anonymous_sessions)} hint="публичный чат" />
        <StatCard label="Студенты" icon="users" value={formatNumber(summary?.authenticated_sessions)} hint={summary ? `${formatNumber(summary.unique_users)} уникальных` : undefined} />
      </div>

      <Tabs<Tab>
        value={tab}
        onChange={setTab}
        items={[
          { value: "sessions", label: "Диалоги", icon: "chat" },
          { value: "contacts", label: "Контакты абитуриентов", icon: "phone", count: contacts.length },
        ]}
      />

      {tab === "sessions" ? (
        <SessionsTab onOpen={(session, query) => setSelected({ session, query: query ?? null })} />
      ) : (
        <ContactsTab contacts={contacts} isLoading={contactsQuery.isLoading} error={contactsQuery.error as Error | null} onOpen={openContact} />
      )}

      {selected ? <SessionDrawer session={selected.session} initialQuery={selected.query} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}
