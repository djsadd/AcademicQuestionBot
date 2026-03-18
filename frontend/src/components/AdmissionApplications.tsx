import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAdmissionApplications } from "../api/admin";
import type { AdmissionApplication } from "../types";
import { formatDate } from "../utils/format";

const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;

const LEVEL_LABELS: Record<string, string> = {
  bachelor: "Бакалавриат",
  master: "Магистратура",
  doctorate: "Докторантура",
  second_higher: "Второе высшее",
};

export function AdmissionApplications() {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState<number>(20);

  const applicationsQuery = useQuery({
    queryKey: ["admission-applications", page, perPage],
    queryFn: () => fetchAdmissionApplications(page, perPage),
    placeholderData: (previousData) => previousData,
  });

  const data = applicationsQuery.data;
  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const pages = data?.pages ?? 0;
  const total = data?.total ?? 0;

  return (
    <section className="feature-section">
      <div className="feature-section__header">
        <div>
          <p className="eyebrow">Admissions</p>
          <h2>Заявки на поступление</h2>
          <p className="muted">
            Список заявок, созданных агентом приемной комиссии, с пагинацией по данным из базы.
          </p>
        </div>
        <span className="feature-section__status">{total} total</span>
      </div>

      <div className="panel">
        <div className="admin-toolbar">
          <div className="admin-toolbar__summary">
            <strong>Всего заявок: {total}</strong>
            <span className="muted">
              Страница {data?.page ?? page}
              {pages > 0 ? ` из ${pages}` : ""}
            </span>
          </div>

          <label className="admin-toolbar__control">
            <span>На странице</span>
            <select
              value={perPage}
              onChange={(event) => {
                const nextPerPage = Number(event.target.value);
                setPerPage(nextPerPage);
                setPage(1);
              }}
            >
              {PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>

        {applicationsQuery.isLoading ? (
          <p>Загрузка заявок...</p>
        ) : applicationsQuery.isError ? (
          <p className="error">Не удалось загрузить список заявок.</p>
        ) : items.length === 0 ? (
          <p className="muted">Заявок пока нет.</p>
        ) : (
          <>
            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>Заявка</th>
                    <th>Абитуриент</th>
                    <th>Контакты</th>
                    <th>Поступление</th>
                    <th>Статус</th>
                    <th>Создана</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <div className="doc-name">
                          <strong>{item.id}</strong>
                          <small>Канал: {item.channel ?? "-"}</small>
                          <small>Telegram ID: {item.telegram_id ?? "-"}</small>
                        </div>
                      </td>
                      <td>
                        <div className="doc-name">
                          <strong>{item.full_name}</strong>
                          <small>ИИН: {item.iin || "-"}</small>
                          <small>Дата рождения: {item.birth_date || "-"}</small>
                        </div>
                      </td>
                      <td>
                        <div className="doc-name">
                          <strong>{item.phone}</strong>
                          <small>{item.email || "-"}</small>
                          {item.comment ? <small>Комментарий: {item.comment}</small> : null}
                        </div>
                      </td>
                      <td>
                        <div className="doc-name">
                          <strong>{item.program}</strong>
                          <small>{LEVEL_LABELS[item.education_level] ?? item.education_level}</small>
                          <small>
                            Язык: {item.study_language || "-"} | Форма: {item.study_format || "-"}
                          </small>
                        </div>
                      </td>
                      <td>
                        <span className={`status-pill status-${item.status.toLowerCase()}`}>
                          {item.status}
                        </span>
                      </td>
                      <td>{formatDate(item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <button
                className="ghost"
                onClick={() => setPage((current) => Math.max(current - 1, 1))}
                disabled={page <= 1}
              >
                Назад
              </button>
              <span className="pagination__status">
                Страница {data?.page ?? page}
                {pages > 0 ? ` из ${pages}` : ""}
              </span>
              <button
                className="ghost"
                onClick={() => setPage((current) => current + 1)}
                disabled={pages > 0 ? page >= pages : items.length < perPage}
              >
                Вперед
              </button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
