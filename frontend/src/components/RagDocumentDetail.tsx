import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchDocumentChunks, fetchDocumentDetail } from "../api/rag";
import type { RagChunk } from "../types";
import { formatBytes, formatDate } from "../utils/format";

export function RagDocumentDetail() {
  const { documentId } = useParams();

  const documentQuery = useQuery({
    queryKey: ["rag-document", documentId],
    queryFn: () => fetchDocumentDetail(documentId ?? ""),
    enabled: Boolean(documentId),
  });

  const chunksQuery = useQuery({
    queryKey: ["rag-document-chunks", documentId],
    queryFn: () => fetchDocumentChunks(documentId ?? "", 200),
    enabled: Boolean(documentId),
  });

  const document = documentQuery.data;
  const chunks = useMemo(() => chunksQuery.data ?? [], [chunksQuery.data]);

  if (!documentId) {
    return (
      <section className="panel">
        <p className="error">Document id is missing.</p>
        <Link className="ghost" to="/rag">
          Back to documents
        </Link>
      </section>
    );
  }

  return (
    <section className="doc-detail">
      <header className="doc-detail__header">
        <div>
          <p className="eyebrow">RAG Document</p>
          <h2>{document?.original_file ?? "Loading..."}</h2>
          <p className="muted">ID: {documentId}</p>
        </div>
        <Link className="ghost" to="/rag">
          Back to documents
        </Link>
      </header>

      <div className="panel">
        <h3>Details</h3>
        {documentQuery.isLoading ? (
          <p>Loading document...</p>
        ) : documentQuery.isError || !document ? (
          <p className="error">Failed to load document details.</p>
        ) : (
          <div className="doc-meta-grid">
            <div>
              <strong>Original file</strong>
              <p className="muted">{document.original_file}</p>
            </div>
            <div>
              <strong>Stored file</strong>
              <p className="muted">{document.stored_file}</p>
            </div>
            <div>
              <strong>Size</strong>
              <p className="muted">{formatBytes(document.size_bytes)}</p>
            </div>
            <div>
              <strong>Chunks</strong>
              <p className="muted">{document.chunks}</p>
            </div>
            <div>
              <strong>Uploaded</strong>
              <p className="muted">{formatDate(document.uploaded_at)}</p>
            </div>
            <div>
              <strong>Status</strong>
              <p className="muted">{document.status ?? "unknown"}</p>
            </div>
            <div>
              <strong>Job id</strong>
              <p className="muted">{document.job_id ?? "-"}</p>
            </div>
            <div>
              <strong>Error</strong>
              <p className="muted">{document.error ?? "-"}</p>
            </div>
            <div className="doc-meta-grid__full">
              <strong>Metadata</strong>
              <pre className="doc-meta__json">
                {JSON.stringify(document.metadata ?? {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Qdrant chunks</h3>
        {chunksQuery.isLoading ? (
          <p>Loading chunks...</p>
        ) : chunksQuery.isError ? (
          <p className="error">Failed to load chunks.</p>
        ) : chunks.length === 0 ? (
          <p className="muted">No chunks found.</p>
        ) : (
          <div className="chunk-grid">
            {chunks.map((chunk: RagChunk, index: number) => {
              const chunkIndex = chunk.metadata?.chunk_index;
              const offset = chunk.metadata?.offset;
              const label =
                typeof chunkIndex === "number"
                  ? `Chunk ${chunkIndex}`
                  : `Chunk ${index + 1}`;
              return (
                <article className="chunk-card" key={chunk.id}>
                  <div className="chunk-card__header">
                    <strong>{label}</strong>
                    {typeof offset === "number" && <span>Offset {offset}</span>}
                  </div>
                  <p className="chunk-card__content">{chunk.content}</p>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
