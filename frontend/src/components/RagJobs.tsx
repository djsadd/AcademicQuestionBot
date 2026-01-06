import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchJobs } from "../api/rag";
import type { RagJob } from "../types";
import { formatDate } from "../utils/format";

interface RagJobsProps {
  sectionId?: string;
}

export function RagJobs({ sectionId }: RagJobsProps) {
  const jobsQuery = useQuery({
    queryKey: ["rag-jobs"],
    queryFn: fetchJobs,
    refetchInterval: 4000,
  });

  const jobs = useMemo(() => jobsQuery.data ?? [], [jobsQuery.data]);

  return (
    <section className="rag-jobs" id={sectionId}>
      <header className="section-header">
        <div>
          <p className="eyebrow">RAG</p>
          <h2>Ingestion jobs</h2>
          <p className="muted">Monitor ingestion status and inspect job errors.</p>
        </div>
      </header>

      <div className="panel">
        {jobsQuery.isLoading ? (
          <p>Loading jobs...</p>
        ) : jobs.length === 0 ? (
          <p className="muted">No jobs yet.</p>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Started</th>
                  <th>Finished</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job: RagJob) => (
                  <tr key={job.job_id}>
                    <td>
                      <div className="doc-name">
                        <strong>{job.original_file}</strong>
                        <small>Job ID: {job.job_id}</small>
                        {job.document_id && <small>Doc ID: {job.document_id}</small>}
                      </div>
                    </td>
                    <td>
                      <span className={`status-pill status-${job.status.toLowerCase()}`}>
                        {job.status}
                      </span>
                    </td>
                    <td>{formatDate(job.created_at ?? "")}</td>
                    <td>{formatDate(job.started_at ?? "")}</td>
                    <td>{formatDate(job.finished_at ?? "")}</td>
                    <td>{job.error || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
