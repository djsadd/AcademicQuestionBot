import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, fetchDocuments, fetchIngestionStatus, uploadDocument } from "../api/rag";
import type { RagDocument } from "../types";
import { formatBytes, formatDate } from "../utils/format";

interface RagManagerProps {
  sectionId?: string;
}

export function RagManager({ sectionId }: RagManagerProps) {
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [metadataRaw, setMetadataRaw] = useState("{}");
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<{
    taskId: string;
    documentId: string;
    fileName: string;
    storedFile: string;
    sizeBytes: number;
  } | null>(null);

  const documentsQuery = useQuery({
    queryKey: ["rag-documents"],
    queryFn: fetchDocuments,
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) {
        throw new Error("Select a file to upload.");
      }
      let metadata: Record<string, unknown> | undefined;
      if (metadataRaw.trim()) {
        try {
          metadata = JSON.parse(metadataRaw);
          setMetadataError(null);
        } catch (error) {
          setMetadataError("Metadata must be valid JSON.");
          throw error;
        }
      }
      return uploadDocument(selectedFile, metadata);
    },
    onSuccess: (data) => {
      const fileSize = selectedFile?.size ?? 0;
      setSelectedFile(null);
      setMetadataRaw("{}");
      setActiveTask({
        taskId: data.task_id,
        documentId: data.document_id,
        fileName: data.file_name,
        storedFile: data.stored_file,
        sizeBytes: fileSize,
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => deleteDocument(documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["rag-documents"] }),
  });

  const taskStatusQuery = useQuery({
    queryKey: ["rag-ingest-status", activeTask?.taskId],
    queryFn: () => fetchIngestionStatus(activeTask!.taskId),
    enabled: Boolean(activeTask?.taskId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) {
        return 2000;
      }
      return data.status === "SUCCESS" || data.status === "FAILURE" ? false : 2000;
    },
  });

  useEffect(() => {
    if (!activeTask) {
      return;
    }
    const status = taskStatusQuery.data?.status;
    if (status === "SUCCESS") {
      queryClient.invalidateQueries({ queryKey: ["rag-documents"] });
    }
  }, [activeTask, queryClient, taskStatusQuery.data?.status]);

  const documents = useMemo(() => documentsQuery.data ?? [], [documentsQuery.data]);
  const hasPending =
    Boolean(activeTask) && !documents.some((doc) => doc.document_id === activeTask?.documentId);
  const displayDocuments = useMemo(() => {
    if (!activeTask || !hasPending) {
      return documents;
    }
    const pendingDoc: RagDocument = {
      document_id: activeTask.documentId,
      original_file: activeTask.fileName,
      stored_file: activeTask.storedFile,
      size_bytes: activeTask.sizeBytes,
      chunks: 0,
      uploaded_at: new Date().toISOString(),
      metadata: { status: "queued" },
    };
    return [pendingDoc, ...documents];
  }, [activeTask, documents, hasPending]);

  const ingestionStatus = taskStatusQuery.data?.status;
  const ingestionResult = taskStatusQuery.data?.result;
  const ingestionError = taskStatusQuery.data?.error;

  return (
    <section className="rag-manager" id={sectionId}>
      <header className="section-header">
        <div>
          <p className="eyebrow">RAG</p>
          <h2>Document ingestion</h2>
          <p className="muted">
            Upload files to add them to the retrieval index. Ingestion runs in the background.
          </p>
        </div>
      </header>

      <div className="panel">
        <h3>Upload document</h3>
        <div className="upload-grid">
          <label className="file-input">
            <span>File</span>
            <input
              type="file"
              accept=".pdf,.doc,.docx,.txt,.md"
              onChange={(event) => {
                const file = event.target.files?.[0];
                setSelectedFile(file ?? null);
              }}
            />
            {selectedFile ? (
              <small>
                Selected file: <strong>{selectedFile.name}</strong>
              </small>
            ) : (
              <small>Pick a file to upload.</small>
            )}
          </label>

          <label className="metadata-input">
            <span>Metadata (JSON)</span>
            <textarea value={metadataRaw} onChange={(e) => setMetadataRaw(e.target.value)} rows={6} />
            {metadataError ? (
              <small className="error">{metadataError}</small>
            ) : (
              <small>Example: {`{ "faculty": "CS" }`}</small>
            )}
          </label>
        </div>
        <div className="actions">
          <button
            className="primary"
            onClick={() => uploadMutation.mutate()}
            disabled={uploadMutation.isPending}
          >
            {uploadMutation.isPending ? "Uploading..." : "Upload"}
          </button>
          {uploadMutation.isSuccess && <span className="success">Upload queued.</span>}
          {uploadMutation.isError && !metadataError && (
            <span className="error">Failed to upload document.</span>
          )}
        </div>
        {activeTask && (
          <div className="status-card">
            <div className="status-card__header">
              <strong>Document ingestion status</strong>
              <span className={`status-pill status-${ingestionStatus?.toLowerCase() || "pending"}`}>
                {ingestionStatus || "PENDING"}
              </span>
            </div>
            <p className="muted">
              {activeTask.fileName} - ID {activeTask.documentId}
            </p>
            {ingestionStatus === "SUCCESS" && (
              <p className="success">
                Ingested successfully: {ingestionResult?.chunks ?? "-"} chunks
              </p>
            )}
            {ingestionStatus === "FAILURE" && (
              <p className="error">Ingestion failed: {ingestionError || "unknown error"}</p>
            )}
          </div>
        )}
      </div>

      <div className="panel">
        <h3>Uploaded documents</h3>
        {documentsQuery.isLoading ? (
          <p>Loading documents...</p>
        ) : displayDocuments.length === 0 ? (
          <p className="muted">No documents yet.</p>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Size</th>
                  <th>Chunks</th>
                  <th>Uploaded</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {displayDocuments.map((doc) => {
                  const status =
                    typeof doc.status === "string"
                      ? doc.status
                      : doc.metadata && typeof doc.metadata.status === "string"
                        ? doc.metadata.status
                        : null;
                  return (
                    <tr key={doc.document_id}>
                      <td>
                        <div className="doc-name">
                          <strong>{doc.original_file}</strong>
                          <small>ID: {doc.document_id}</small>
                          {status && <small>Status: {status}</small>}
                        </div>
                      </td>
                      <td>{formatBytes(doc.size_bytes)}</td>
                      <td>{doc.chunks}</td>
                      <td>{formatDate(doc.uploaded_at)}</td>
                      <td>
                        <div className="table-actions">
                          <Link className="ghost" to={`/rag/${doc.document_id}`}>
                            View
                          </Link>
                          <button
                            className="ghost"
                            onClick={() => deleteMutation.mutate(doc.document_id)}
                            disabled={deleteMutation.isPending}
                          >
                            Delete
                          </button>
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
    </section>
  );
}
