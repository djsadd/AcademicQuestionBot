import { useState, type FormEvent } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { fetchPlatonusSession, fetchStudentAcademicCalendar } from "../api/platonus";
import { Callout, LoadingRows, PageHeader, StatCard } from "./ui/Admin";
import { Icon } from "./ui/Icon";

function formatAge(seconds: number | null) {
  if (seconds === null) return "—";
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes} мин ${seconds % 60} с` : `${seconds} с`;
}

function formatTimestamp(epoch: number | null) {
  if (!epoch) return "—";
  return new Date(epoch * 1000).toLocaleString("ru-RU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

function Check({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li>
      <span className={`health-dot${ok ? " is-ok" : ""}`} />
      <span>{label}</span>
      <span className="muted">{ok ? "есть" : "нет"}</span>
    </li>
  );
}

export function PlatonusStatus() {
  const [personId, setPersonId] = useState("");
  const sessionQuery = useQuery({ queryKey: ["platonus-session"], queryFn: fetchPlatonusSession, refetchInterval: 30_000 });
  const calendar = useMutation({ mutationFn: (id: string) => fetchStudentAcademicCalendar(id, "ru") });
  const status = sessionQuery.data;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (personId.trim()) calendar.mutate(personId.trim());
  };

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Интеграция"
        title="Platonus"
        description="Служебная сессия, через которую ассистент получает персональные данные студентов (календарь, статус)."
        actions={
          <button type="button" className="ghost" onClick={() => sessionQuery.refetch()} disabled={sessionQuery.isFetching}>
            <Icon name="refresh" size={16} /> {sessionQuery.isFetching ? "Обновляем…" : "Обновить"}
          </button>
        }
      />

      {sessionQuery.isLoading ? (
        <LoadingRows rows={1} height={110} />
      ) : sessionQuery.isError ? (
        <Callout tone="danger" title="Сервис Platonus недоступен">{(sessionQuery.error as Error).message}</Callout>
      ) : status ? (
        <>
          {!status.token_present ? (
            <Callout tone="danger" title="Нет активной сессии">Ассистент не сможет показывать студентам календарь. Проверьте PLATONUS_LOGIN / PLATONUS_PASSWORD.</Callout>
          ) : null}
          <div className="stat-grid">
            <StatCard label="Сессия" icon="link" tone={status.token_present ? "success" : "danger"} value={status.token_present ? "Активна" : "Нет"} />
            <StatCard label="Последний вход" icon="clock" value={formatTimestamp(status.last_login)} hint={`возраст ${formatAge(status.age_seconds)}`} />
            <StatCard label="Обновление" icon="refresh" value={`${Math.round(status.refresh_seconds / 60)} мин`} hint="интервал автологина" />
          </div>
          <section className="panel">
            <h3>Параметры сессии</h3>
            <ul className="health-list">
              <Check ok={status.token_present} label="Токен" />
              <Check ok={status.cookie_present} label="Cookie" />
              <Check ok={status.sid_present} label="SID" />
              <Check ok={status.user_agent_present} label="User-Agent" />
            </ul>
          </section>
        </>
      ) : null}

      <section className="panel">
        <div>
          <h3>Проверка календаря студента</h3>
          <p className="muted">Запрос академического календаря по Person ID — так же, как его получает агент деканата.</p>
        </div>
        <form className="search-bar" onSubmit={submit}>
          <Icon name="user" size={18} />
          <input value={personId} onChange={(event) => setPersonId(event.target.value)} placeholder="Person ID, например 20458" aria-label="Person ID" inputMode="numeric" />
          <button type="submit" className="primary" disabled={!personId.trim() || calendar.isPending}>
            {calendar.isPending ? <span className="spinner spinner--on-brand" /> : null} Запросить
          </button>
        </form>
        {calendar.isError ? <Callout tone="danger" title="Ошибка запроса">{(calendar.error as Error).message}</Callout> : null}
        {calendar.data ? <pre className="code-block">{JSON.stringify(calendar.data, null, 2)}</pre> : null}
      </section>
    </div>
  );
}
