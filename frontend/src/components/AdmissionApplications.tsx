import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAdmissionApplications } from "../api/admin";
import { formatDate } from "../utils/format";
import { Callout, EmptyState, LoadingRows, Pagination, StatusBadge } from "./ui/Admin";
import { Icon } from "./ui/Icon";

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
  const query = useQuery({
    queryKey: ["admission-applications", page, perPage],
    queryFn: () => fetchAdmissionApplications(page, perPage),
    placeholderData: (previous) => previous,
  });
  const data = query.data;
  const items = useMemo(() => data?.items ?? [], [data?.items]);

  return (
    <section className="panel">
      <div className="panel__head">
        <div>
          <h3>Заявки на поступление</h3>
          <p className="muted">Заявки, оформленные абитуриентами через ИИ-агента приёмной комиссии.</p>
        </div>
      </div>

      {query.isLoading ? (
        <LoadingRows />
      ) : query.isError ? (
        <Callout tone="danger" title="Не удалось загрузить заявки">{(query.error as Error).message}</Callout>
      ) : !items.length ? (
        <EmptyState icon="file" title="Заявок пока нет" />
      ) : (
        <>
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Абитуриент</th>
                  <th>Контакты</th>
                  <th>Программа</th>
                  <th>Статус</th>
                  <th>Создана</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.full_name}</strong>
                      <div className="muted cell-sub">ИИН {item.iin || "—"} · {item.birth_date || "дата рождения не указана"}</div>
                    </td>
                    <td>
                      <a href={`tel:${item.phone}`} className="nowrap"><Icon name="phone" size={13} /> {item.phone}</a>
                      {item.email ? <div className="cell-sub"><a href={`mailto:${item.email}`}>{item.email}</a></div> : null}
                      {item.comment ? <div className="muted cell-sub">«{item.comment}»</div> : null}
                    </td>
                    <td>
                      <strong>{item.program}</strong>
                      <div className="muted cell-sub">
                        {[LEVEL_LABELS[item.education_level] ?? item.education_level, item.study_language, item.study_format].filter(Boolean).join(" · ")}
                      </div>
                    </td>
                    <td><StatusBadge status={item.status} /></td>
                    <td className="nowrap muted">
                      {formatDate(item.created_at)}
                      <div className="cell-sub">{item.channel ?? ""}</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={data?.page ?? page}
            pages={data?.pages}
            onChange={setPage}
            hasNext={items.length >= perPage}
            total={data?.total}
            perPage={perPage}
            perPageOptions={PAGE_SIZE_OPTIONS}
            onPerPageChange={(value) => {
              setPerPage(value);
              setPage(1);
            }}
          />
        </>
      )}
    </section>
  );
}
