import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchChatAnalyticsSummary } from "../api/admin";
import { API_BASE_URL, apiClient, authStorage } from "../api/client";
import { fetchStats } from "../api/rag";
import { formatNumber, formatRelative } from "../utils/format";
import { Callout, StatCard } from "./ui/Admin";
import { Icon, type IconName } from "./ui/Icon";

type Me = {
  telegram_id: number;
  username?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  person_id?: string | null;
  platonus_auth?: boolean;
  role?: string | null;
  fullname?: string | null;
  statusName?: string | null;
  email?: string | null;
  is_admin?: boolean;
};

type Readiness = { status: string; checks: Record<string, boolean>; vector_mode?: string };

const PROFILE_URL = "https://academiq.tau-edu.kz/#/profile";

const ADMIN_LINKS: { to: string; icon: IconName; title: string; text: string }[] = [
  { to: "/rag", icon: "database", title: "База знаний", text: "Загрузка регламентов, индексация, проверка поиска" },
  { to: "/admissions", icon: "cap", title: "Приёмная комиссия", text: "Программы, цены, проходные баллы, контакты" },
  { to: "/chat-analytics", icon: "chart", title: "Диалоги", text: "Логи чатов, вопросы, оставленные контакты" },
  { to: "/chat-users", icon: "users", title: "Пользователи", text: "Роли и доступ к панели управления" },
  { to: "/agents", icon: "cpu", title: "Агенты", text: "Нагрузка и состояние ИИ-агентов" },
  { to: "/rag-jobs", icon: "layers", title: "Журнал индексации", text: "Статусы и ошибки обработки документов" },
  { to: "/platonus", icon: "link", title: "Platonus", text: "Сессия интеграции и календарь студента" },
];

const CHECK_LABELS: Record<string, string> = { database: "База данных", vector_store: "Векторный индекс", llm_configured: "Языковая модель" };

async function fetchReadiness(): Promise<Readiness> {
  // 503 still carries a JSON body describing which dependency is down.
  const response = await fetch(`${API_BASE_URL}/health/ready`);
  return response.json() as Promise<Readiness>;
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "U";
}

function AdminPanel() {
  const statsQuery = useQuery({ queryKey: ["rag-stats"], queryFn: fetchStats });
  const summaryQuery = useQuery({ queryKey: ["chat-summary"], queryFn: fetchChatAnalyticsSummary });
  const healthQuery = useQuery({ queryKey: ["readiness"], queryFn: fetchReadiness, refetchInterval: 30_000 });
  const stats = statsQuery.data;
  const summary = summaryQuery.data;
  const failed = stats?.registry.by_status.failed ?? 0;

  return (
    <>
      <section className="stack">
        <div className="section-title">
          <h3>Панель администратора</h3>
          {healthQuery.data ? (
            <span className={`status-pill ${healthQuery.data.status === "ok" ? "status-success" : "status-failed"}`}>
              {healthQuery.data.status === "ok" ? "Все системы работают" : "Есть проблемы"}
            </span>
          ) : null}
        </div>
        <div className="stat-grid">
          <StatCard label="Диалогов" icon="chat" value={formatNumber(summary?.total_sessions)} hint={summary?.last_event_at ? `последний ${formatRelative(summary.last_event_at)}` : undefined} />
          <StatCard label="Пользователей" icon="users" value={formatNumber(summary?.unique_users)} hint={summary ? `${formatNumber(summary.anonymous_sessions)} анонимных сессий` : undefined} />
          <StatCard label="Документов в базе" icon="database" value={formatNumber(stats?.registry.documents)} hint={stats ? `${formatNumber(stats.index.points ?? stats.registry.chunks)} фрагментов` : undefined} />
          <StatCard label="Ошибки индексации" icon="alert" tone={failed ? "danger" : "success"} value={formatNumber(failed)} hint={failed ? <Link to="/rag">исправить →</Link> : "нет"} />
        </div>
        {healthQuery.data && healthQuery.data.status !== "ok" ? (
          <Callout tone="danger" title="Не все зависимости доступны">
            {Object.entries(healthQuery.data.checks)
              .filter(([, ok]) => !ok)
              .map(([key]) => CHECK_LABELS[key] ?? key)
              .join(", ")}
          </Callout>
        ) : null}
        {stats?.index.dimension_mismatch ? (
          <Callout tone="danger" title="Поиск по документам не работает" action={<Link to="/rag" className="primary btn--sm">Открыть базу знаний</Link>}>
            Индекс создан для другой модели эмбеддингов — его нужно пересоздать.
          </Callout>
        ) : null}
      </section>

      <section className="admin-links">
        {ADMIN_LINKS.map((item) => (
          <Link key={item.to} to={item.to} className="admin-link">
            <span className="admin-link__icon"><Icon name={item.icon} size={20} /></span>
            <span className="admin-link__text">
              <strong>{item.title}</strong>
              <span>{item.text}</span>
            </span>
            <Icon name="chevronRight" size={16} className="admin-link__arrow" />
          </Link>
        ))}
      </section>

      {healthQuery.data ? (
        <section className="panel">
          <h3>Состояние системы</h3>
          <ul className="health-list">
            {Object.entries(healthQuery.data.checks).map(([key, ok]) => (
              <li key={key}>
                <span className={`health-dot${ok ? " is-ok" : ""}`} />
                <span>{CHECK_LABELS[key] ?? key}</span>
                <span className="muted">{ok ? "работает" : key === "llm_configured" ? "не настроена" : "недоступно"}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

export function Profile() {
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);
  const meQuery = useQuery({ queryKey: ["me"], queryFn: () => apiClient.get<{ user: Me }>("/auth/me").then((data) => data.user) });
  const me = meQuery.data;

  const logout = async () => {
    setLoggingOut(true);
    const refreshToken = authStorage.getRefreshToken();
    try {
      if (refreshToken) await apiClient.post("/auth/logout", JSON.stringify({ refresh_token: refreshToken }));
    } catch {
      // Tokens are cleared locally anyway.
    } finally {
      authStorage.clearTokens();
      navigate("/telegram-login", { replace: true });
    }
  };

  if (meQuery.isLoading) return <div className="page-loader"><span className="spinner" /></div>;
  if (!me) return <Callout tone="danger" title="Не удалось загрузить профиль">{(meQuery.error as Error | null)?.message}</Callout>;

  const name = me.fullname?.trim() || [me.first_name, me.last_name].filter(Boolean).join(" ") || me.username || "Пользователь";
  const details: [string, string | null | undefined][] = [
    ["Логин", me.username],
    ["Email", me.email],
    ["Статус", me.statusName],
    ["Роль", me.role],
    ["Platonus Person ID", me.person_id],
  ];

  return (
    <div className="stack-lg">
      <section className="profile-hero">
        <span className="profile-hero__avatar">{initials(name)}</span>
        <div className="profile-hero__text">
          <h2>{name}</h2>
          <div className="profile-hero__badges">
            {me.is_admin ? <span className="tag tag--brand"><Icon name="shield" size={13} /> Администратор</span> : null}
            <span className={`tag${me.platonus_auth ? " tag--success" : ""}`}>
              <Icon name={me.platonus_auth ? "check" : "link"} size={13} /> {me.platonus_auth ? "Platonus подключён" : "Platonus не подключён"}
            </span>
            {me.statusName ? <span className="tag">{me.statusName}</span> : null}
          </div>
        </div>
        <div className="profile-hero__actions">
          <Link to="/chat" className="primary"><Icon name="sparkles" size={16} /> Открыть чат</Link>
          <a className="ghost" href={PROFILE_URL} target="_blank" rel="noreferrer"><Icon name="external" size={16} /> Кабинет Academiq</a>
          <button type="button" className="ghost btn--danger" onClick={logout} disabled={loggingOut}><Icon name="logout" size={16} /> {loggingOut ? "Выходим…" : "Выйти"}</button>
        </div>
      </section>

      <section className="panel">
        <h3>Данные аккаунта</h3>
        <dl className="kv kv--wide">
          {details.map(([label, value]) => (
            <div key={label} className="kv__row">
              <dt>{label}</dt>
              <dd>{value || <span className="muted">—</span>}</dd>
            </div>
          ))}
        </dl>
        {!me.platonus_auth ? <p className="muted">Персональные данные (календарь, статус) доступны после входа через логин и пароль Platonus.</p> : null}
      </section>

      {me.is_admin ? <AdminPanel /> : null}
    </div>
  );
}
