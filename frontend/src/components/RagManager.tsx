import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, fetchDocuments, uploadDocument } from "../api/rag";
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

  const documentsQuery = useQuery({
    queryKey: ["rag-documents"],
    queryFn: fetchDocuments,
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) {
        throw new Error("Выберите файл для загрузки");
      }
      let metadata: Record<string, unknown> | undefined;
      if (metadataRaw.trim()) {
        try {
          metadata = JSON.parse(metadataRaw);
          setMetadataError(null);
        } catch (error) {
          setMetadataError("Некорректный JSON для метаданных");
          throw error;
        }
      }
      return uploadDocument(selectedFile, metadata);
    },
    onSuccess: () => {
      setSelectedFile(null);
      setMetadataRaw("{}");
      queryClient.invalidateQueries({ queryKey: ["rag-documents"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => deleteDocument(documentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["rag-documents"] }),
  });

  const documents = useMemo(() => documentsQuery.data ?? [], [documentsQuery.data]);

  return (
    <section className="rag-manager" id={sectionId}>
      <header className="section-header">
        <div>
          <p className="eyebrow">RAG</p>
          <h2>Управление документами</h2>
          <p className="muted">
            Загрузите регламенты и методички, чтобы боты могли ссылаться на актуальные данные.
          </p>
        </div>
      </header>

      <div className="panel">
        <h3>Загрузка документа</h3>
        <div className="upload-grid">
          <label className="file-input">
            <span>Файл</span>
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
                Выбран файл: <strong>{selectedFile.name}</strong>
              </small>
            ) : (
              <small>Максимальный размер определяется настройками сервера</small>
            )}
          </label>

          <label className="metadata-input">
            <span>Доп. метаданные (JSON)</span>
            <textarea
              value={metadataRaw}
              onChange={(e) => setMetadataRaw(e.target.value)}
              rows={6}
            />
            {metadataError ? (
              <small className="error">{metadataError}</small>
            ) : (
              <small>Например, {`{ "faculty": "CS" }`}</small>
            )}
          </label>
        </div>
        <div className="actions">
          <button
            className="primary"
            onClick={() => uploadMutation.mutate()}
            disabled={uploadMutation.isPending}
          >
            {uploadMutation.isPending ? "Загрузка..." : "Загрузить"}
          </button>
          {uploadMutation.isSuccess && <span className="success">Документ добавлен!</span>}
          {uploadMutation.isError && !metadataError && (
            <span className="error">Не удалось загрузить документ</span>
          )}
        </div>
      </div>

      <div className="panel">
        <h3>Загруженные файлы</h3>
        {documentsQuery.isLoading ? (
          <p>Загрузка списка...</p>
        ) : documents.length === 0 ? (
          <p className="muted">Документы пока не добавлены.</p>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Файл</th>
                  <th>Размер</th>
                  <th>Фрагменты</th>
                  <th>Добавлен</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc.document_id}>
                    <td>
                      <div className="doc-name">
                        <strong>{doc.original_file}</strong>
                        <small>ID: {doc.document_id}</small>
                      </div>
                    </td>
                    <td>{formatBytes(doc.size_bytes)}</td>
                    <td>{doc.chunks}</td>
                    <td>{formatDate(doc.uploaded_at)}</td>
                    <td>
                      <button
                        className="ghost"
                        onClick={() => deleteMutation.mutate(doc.document_id)}
                        disabled={deleteMutation.isPending}
                      >
                        Удалить
                      </button>
                    </td>
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
