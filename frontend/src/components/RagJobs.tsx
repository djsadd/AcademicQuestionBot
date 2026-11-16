import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchJobs } from "../api/rag";
import { formatBytes, formatDate } from "../utils/format";
import { Callout, EmptyState, PageHeader, StatusBadge } from "./ui/Admin";

const ACTIVE = new Set(["queued", "processing"]);

function duration(start?: string | null, end?: string | null) {
  if (!start || !end) return "—";
  const seconds = Math.max(0, (new Date(end).getTime() - new Date(start).getTime()) / 1000);
  return seconds < 60 ? `${seconds.toFixed(seconds < 10 ? 1 : 0)} с` : `${Math.floor(seconds / 60)} мин ${Math.round(seconds % 60)} с`;
}

export function RagJobs() {
  const jobsQuery = useQuery({
    queryKey: ["rag-jobs"],
    queryFn: fetchJobs,
    refetchInterval: (query) => ((query.state.data ?? []).some((job) => ACTIVE.has(job.status)) ? 2500 : 15_000),
  });
  const jobs = useMemo(() => jobsQuery.data ?? [], [jobsQuery.data]);

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="RAG"
        title="Журнал индексации"
        description="Каждая загрузка и переиндексация документа. Ошибки здесь объясняют, почему документ не попал в поиск."
        actions={<Link to="/rag" className="ghost">К базе знаний</Link>}
      />
      <section className="panel">
        {jobsQuery.isLoading ? (
          <div className="skeleton-list">{[0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 48 }} />)}</div>
        ) : jobsQuery.isError ? (
          <Callout tone="danger" title="Не удалось загрузить журнал">{(jobsQuery.error as Error).message}</Callout>
        ) : !jobs.length ? (
          <EmptyState icon="layers" title="Задач пока нет" text="Они появятся после загрузки первого документа." />
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Файл</th>
                  <th>Статус</th>
                  <th>Создана</th>
                  <th>Длительность</th>
                  <th>Ошибка</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id}>
                    <td>
                      <div>
                        {job.document_id ? <Link to={`/rag/${job.document_id}`}><strong>{job.original_file}</strong></Link> : <strong>{job.original_file}</strong>}
                        <div className="muted cell-sub">{formatBytes(job.size_bytes)}</div>
                      </div>
                    </td>
                    <td><StatusBadge status={job.status} /></td>
                    <td className="nowrap muted">{formatDate(job.created_at)}</td>
                    <td className="nowrap">{duration(job.started_at, job.finished_at)}</td>
                    <td>{job.error ? <span className="cell-error cell-error--wrap">{job.error}</span> : <span className="muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
