import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAdminUsers, updateAdminUserRole } from "../api/admin";
import type { AdminUser } from "../types";
import { formatNumber, formatRelative } from "../utils/format";
import { Callout, EmptyState, LoadingRows, PageHeader, StatCard } from "./ui/Admin";
import { Icon } from "./ui/Icon";

const ROLE_OPTIONS = [
  { value: "", label: "Без роли" },
  { value: "student", label: "Студент" },
  { value: "teacher", label: "Преподаватель" },
  { value: "staff", label: "Сотрудник" },
  { value: "deanery", label: "Деканат" },
  { value: "admin", label: "Администратор" },
];
const ADMIN_ROLES = new Set(["admin", "administrator", "superuser", "staff", "dean", "deanery"]);

const displayName = (user: AdminUser) =>
  user.platonus_fullname || [user.first_name, user.last_name].filter(Boolean).join(" ") || user.username || user.platonus_email || `Пользователь ${user.telegram_id}`;

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "U";

function RoleEditor({ user }: { user: AdminUser }) {
  const queryClient = useQueryClient();
  const [role, setRole] = useState(user.platonus_role ?? "");
  const [saved, setSaved] = useState(false);
  const mutation = useMutation({
    mutationFn: () => updateAdminUserRole(user.telegram_id, role || null),
    onSuccess: () => {
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });
  const changed = role !== (user.platonus_role ?? "");
  const known = ROLE_OPTIONS.some((option) => option.value === role);

  return (
    <div className="role-editor">
      <select value={role} onChange={(event) => setRole(event.target.value)} disabled={mutation.isPending} aria-label="Роль">
        {!known ? <option value={role}>{role}</option> : null}
        {ROLE_OPTIONS.map((option) => <option key={option.value || "none"} value={option.value}>{option.label}</option>)}
      </select>
      {changed ? (
        <button type="button" className="primary btn--sm" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
          {mutation.isPending ? "…" : "Сохранить"}
        </button>
      ) : saved ? (
        <span className="success role-editor__ok"><Icon name="check" size={14} /> Сохранено</span>
      ) : null}
      {mutation.isError ? <span className="error role-editor__err">{(mutation.error as Error).message}</span> : null}
    </div>
  );
}

export function ChatUsers() {
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const usersQuery = useQuery({ queryKey: ["admin-users"], queryFn: () => fetchAdminUsers(200) });
  const users = useMemo(() => usersQuery.data?.items ?? [], [usersQuery.data]);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return users.filter((user) => {
      if (roleFilter === "admins" && !ADMIN_ROLES.has((user.platonus_role ?? "").toLowerCase())) return false;
      if (roleFilter === "none" && user.platonus_role) return false;
      if (!needle) return true;
      return [displayName(user), user.username, user.platonus_email, user.platonus_iin, String(user.telegram_id)]
        .some((value) => String(value ?? "").toLowerCase().includes(needle));
    });
  }, [users, search, roleFilter]);

  const admins = users.filter((user) => ADMIN_ROLES.has((user.platonus_role ?? "").toLowerCase())).length;
  const platonus = users.filter((user) => user.platonus_auth).length;
  const activeWeek = users.filter((user) => user.last_seen && Date.now() - new Date(user.last_seen).getTime() < 7 * 86_400_000).length;

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="Доступ"
        title="Пользователи"
        description="Все, кто входил в кабинет. Здесь назначаются роли: администраторы видят базу знаний, аналитику и настройки."
      />

      <div className="stat-grid">
        <StatCard label="Пользователей" icon="users" value={formatNumber(users.length)} />
        <StatCard label="Активны за 7 дней" icon="activity" tone="brand" value={formatNumber(activeWeek)} />
        <StatCard label="Через Platonus" icon="link" tone="success" value={formatNumber(platonus)} />
        <StatCard label="Администраторов" icon="shield" value={formatNumber(admins)} />
      </div>

      <section className="panel">
        <div className="toolbar">
          <label className="toolbar__search">
            <Icon name="search" size={16} />
            <input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Имя, логин, email, ИИН" />
          </label>
          <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)} aria-label="Фильтр по роли">
            <option value="">Все пользователи</option>
            <option value="admins">Администраторы</option>
            <option value="none">Без роли</option>
          </select>
        </div>

        {usersQuery.isLoading ? (
          <LoadingRows />
        ) : usersQuery.isError ? (
          <Callout tone="danger" title="Не удалось загрузить пользователей">{(usersQuery.error as Error).message}</Callout>
        ) : !filtered.length ? (
          <EmptyState icon="users" title={users.length ? "Никого не найдено" : "Пользователей пока нет"} />
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Пользователь</th>
                  <th>Platonus</th>
                  <th className="num">Диалоги</th>
                  <th>Был в сети</th>
                  <th>Роль</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((user) => {
                  const name = displayName(user);
                  return (
                    <tr key={user.telegram_id}>
                      <td>
                        <div className="person">
                          <span className="person__avatar">{initials(name)}</span>
                          <span className="person__text">
                            <strong>{name}</strong>
                            <span>{user.platonus_email || user.username || `ID ${user.telegram_id}`}</span>
                          </span>
                        </div>
                      </td>
                      <td>
                        {user.platonus_auth ? <span className="tag tag--success"><Icon name="check" size={12} /> подключён</span> : <span className="tag tag--muted">нет</span>}
                        {user.platonus_status_name ? <div className="muted cell-sub">{user.platonus_status_name}</div> : null}
                      </td>
                      <td className="num">
                        {formatNumber(user.session_count)}
                        <div className="muted cell-sub">{formatNumber(user.event_count)} сообщ.</div>
                      </td>
                      <td className="nowrap muted">{user.last_seen ? formatRelative(user.last_seen) : "—"}</td>
                      <td><RoleEditor key={`${user.telegram_id}-${user.platonus_role}`} user={user} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
