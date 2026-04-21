import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAdminUsers, updateAdminUserRole } from "../api/admin";
import type { AdminUser } from "../types";
import { formatDate } from "../utils/format";

const ROLE_OPTIONS = [
  { value: "", label: "Без роли" },
  { value: "student", label: "student" },
  { value: "teacher", label: "teacher" },
  { value: "staff", label: "staff" },
  { value: "deanery", label: "deanery" },
  { value: "admin", label: "admin" },
];

function getDisplayName(user: AdminUser) {
  return (
    user.platonus_fullname ||
    [user.first_name, user.last_name].filter(Boolean).join(" ") ||
    user.username ||
    user.platonus_email ||
    `User ${user.telegram_id}`
  );
}

function ChatUsersPanel({ userItems }: { userItems: AdminUser[] }) {
  const queryClient = useQueryClient();
  const [draftRoles, setDraftRoles] = useState<Record<number, string>>({});
  const [updatedUserId, setUpdatedUserId] = useState<number | null>(null);

  useEffect(() => {
    setDraftRoles((current) => {
      const next: Record<number, string> = {};
      for (const item of userItems) {
        next[item.telegram_id] = current[item.telegram_id] ?? item.platonus_role ?? "";
      }
      return next;
    });
  }, [userItems]);

  const updateRoleMutation = useMutation({
    mutationFn: ({ telegramId, role }: { telegramId: number; role: string | null }) =>
      updateAdminUserRole(telegramId, role),
    onSuccess: (response) => {
      const updatedUser = response.user;
      setUpdatedUserId(updatedUser.telegram_id);
      setDraftRoles((current) => ({
        ...current,
        [updatedUser.telegram_id]: updatedUser.platonus_role ?? "",
      }));
      queryClient.setQueryData(["admin-users"], (current: { items?: AdminUser[]; limit?: number } | undefined) => {
        if (!current?.items) return current;
        return {
          ...current,
          items: current.items.map((item) => (
            item.telegram_id === updatedUser.telegram_id ? updatedUser : item
          )),
        };
      });
      void queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  function handleSave(item: AdminUser) {
    const draftRole = (draftRoles[item.telegram_id] ?? "").trim();
    setUpdatedUserId(null);
    updateRoleMutation.mutate({
      telegramId: item.telegram_id,
      role: draftRole || null,
    });
  }

  return (
    <div className="panel">
      <div className="feature-section__header">
        <div>
          <p className="eyebrow">Users</p>
          <h3>Пользователи чата</h3>
          <p className="muted">Список аккаунтов с идентификаторами, активностью и ручным назначением ролей.</p>
        </div>
        <span className="muted">{userItems.length} записей</span>
      </div>

      {updateRoleMutation.isError ? (
        <p className="error">
          {updateRoleMutation.error instanceof Error
            ? updateRoleMutation.error.message
            : "Не удалось обновить роль пользователя."}
        </p>
      ) : null}

      {userItems.length === 0 ? (
        <p className="muted">Пользователей пока нет.</p>
      ) : (
        <div className="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Идентификаторы</th>
                <th>Активность</th>
                <th>Назначение роли</th>
              </tr>
            </thead>
            <tbody>
              {userItems.map((item) => {
                const draftRole = draftRoles[item.telegram_id] ?? item.platonus_role ?? "";
                const isChanged = draftRole !== (item.platonus_role ?? "");

                return (
                  <tr key={item.telegram_id}>
                    <td>
                      <div className="doc-name">
                        <strong>{getDisplayName(item)}</strong>
                        <small>{item.platonus_email || item.username || "Email или логин не указан"}</small>
                        <small>
                          Статус: {item.platonus_status_name || (item.platonus_auth ? "Авторизован" : "Не авторизован")}
                        </small>
                      </div>
                    </td>
                    <td>
                      <div className="doc-name">
                        <small>Telegram ID: {item.telegram_id}</small>
                        <small>Person ID: {item.platonus_person_id ?? "-"}</small>
                        <small>ИИН: {item.platonus_iin ?? "-"}</small>
                      </div>
                    </td>
                    <td>
                      <div className="doc-name">
                        <small>События: {item.event_count}</small>
                        <small>Сессии: {item.session_count}</small>
                        <small>Последняя активность: {item.last_seen ? formatDate(item.last_seen) : "-"}</small>
                      </div>
                    </td>
                    <td>
                      <div className="doc-name">
                        <select
                          value={draftRole}
                          onChange={(event) =>
                            setDraftRoles((current) => ({
                              ...current,
                              [item.telegram_id]: event.target.value,
                            }))
                          }
                          disabled={updateRoleMutation.isPending}
                        >
                          {ROLE_OPTIONS.map((option) => (
                            <option key={option.value || "empty"} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                        <button
                          className="ghost"
                          onClick={() => handleSave(item)}
                          disabled={updateRoleMutation.isPending || !isChanged}
                        >
                          {updateRoleMutation.isPending ? "Сохранение..." : "Сохранить"}
                        </button>
                        <small>Текущая роль: {item.platonus_role || "-"}</small>
                        {updatedUserId === item.telegram_id ? <small>Роль обновлена.</small> : null}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function ChatUsers() {
  const usersQuery = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => fetchAdminUsers(200),
  });

  return (
    <section className="feature-section">
      <div className="feature-section__header">
        <div>
          <p className="eyebrow">Users</p>
          <h2>Пользователи</h2>
          <p className="muted">Раздел администрирования пользователей: список аккаунтов, активность и назначение ролей.</p>
        </div>
        <span className="feature-section__status">
          {usersQuery.data?.items.length ?? 0} users
        </span>
      </div>

      {usersQuery.isLoading ? (
        <p>Загрузка пользователей...</p>
      ) : usersQuery.isError ? (
        <p className="error">Не удалось загрузить список пользователей.</p>
      ) : (
        <ChatUsersPanel userItems={usersQuery.data?.items ?? []} />
      )}
    </section>
  );
}
