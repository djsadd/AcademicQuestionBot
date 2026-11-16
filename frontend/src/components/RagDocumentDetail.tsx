import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, downloadDocument, fetchDocumentChunks, fetchDocumentDetail, fetchStats, reindexDocument, updateDocument } from "../api/rag";
import { formatBytes, formatDate, formatNumber } from "../utils/format";
import { Callout, EmptyState, PageHeader, StatusBadge } from "./ui/Admin";
import { Icon } from "./ui/Icon";

const ACTIVE = new Set(["queued", "processing"]);

export function RagDocumentDetail() {
  const { documentId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [chunkFilter, setChunkFilter] = useState("");
  const [form, setForm] = useState({ title: "", category: "other", audience: "all", description: "" });
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const statsQuery = useQuery({ queryKey: ["rag-stats"], queryFn: fetchStats });
  const documentQuery = useQuery({
    queryKey: ["rag-document", documentId],
    queryFn: () => fetchDocumentDetail(documentId),
    enabled: Boolean(documentId),
    refetchInterval: (query) => (ACTIVE.has(query.state.data?.status ?? "") ? 2500 : false),
  });
  const doc = documentQuery.data;
  const chunksQuery = useQuery({
    queryKey: ["rag-document-chunks", documentId, doc?.status, doc?.indexed_at],
    queryFn: () => fetchDocumentChunks(documentId),
    enabled: Boolean(documentId) && doc?.status === "ingested",
  });

  useEffect(() => {
    if (!doc) return;
    setForm({
      title: doc.title ?? doc.original_file,
      category: doc.category ?? "other",
      audience: doc.audience ?? "all",
      description: String(doc.metadata?.description ?? ""),
    });
  }, [doc?.document_id, doc?.title, doc?.category, doc?.audience]); // eslint-disable-line react-hooks/exhaustive-deps

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["rag-document", documentId] });
    queryClient.invalidateQueries({ queryKey: ["rag-documents"] });
  };
  const onError = (err: unknown) => setError(err instanceof Error ? err.message : "Действие не выполнено.");

  const saveMutation = useMutation({
    mutationFn: () => updateDocument(documentId, form),
    onSuccess: (data) => {
      invalidate();
      setSaved(data.reindex_recommended ? "Сохранено. Переиндексируйте документ, чтобы новое название учитывалось в поиске." : "Сохранено.");
    },
    onError,
  });
  const reindexMutation = useMutation({ mutationFn: () => reindexDocument(documentId), onSuccess: () => { setSaved(null); invalidate(); }, onError });
  const deleteMutation = useMutation({
    mutationFn: () => deleteDocument(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rag-documents"] });
      navigate("/rag", { replace: true });
    },
    onError,
  });

  const chunks = useMemo(() => {
    const needle = chunkFilter.trim().toLowerCase();
    const list = chunksQuery.data ?? [];
    return needle ? list.filter((chunk) => chunk.content.toLowerCase().includes(needle)) : list;
  }, [chunksQuery.data, chunkFilter]);

  if (documentQuery.isLoading) return <div className="page-loader"><span className="spinner" /></div>;
  if (!doc) {
    return (
      <EmptyState
        icon="file"
        title="Документ не найден"
        text={documentQuery.error instanceof Error ? documentQuery.error.message : undefined}
        action={<Link to="/rag" className="ghost">К базе знаний</Link>}
      />
    );
  }

  const categories = statsQuery.data?.categories ?? { other: "Другое" };
  const audiences = statsQuery.data?.audiences ?? { all: "Все" };
  const busy = ACTIVE.has(doc.status ?? "");

  return (
    <div className="stack-lg">
      <Link to="/rag" className="back-link"><Icon name="arrowRight" size={14} style={{ transform: "rotate(180deg)" }} /> База знаний</Link>
      <PageHeader
        title={doc.title ?? doc.original_file}
        description={<>{doc.original_file} · {formatBytes(doc.size_bytes)} · загружен {formatDate(doc.uploaded_at)}</>}
        actions={
          <>
            <StatusBadge status={doc.status} />
            <button type="button" className="ghost" onClick={() => downloadDocument(doc).catch(onError)}><Icon name="download" size={16} /> Скачать</button>
            <button type="button" className="ghost" disabled={busy || reindexMutation.isPending} onClick={() => reindexMutation.mutate()}><Icon name="refresh" size={16} /> Переиндексировать</button>
            <button type="button" className="ghost btn--danger" onClick={() => window.confirm("Удалить документ из базы знаний?") && deleteMutation.mutate()}><Icon name="trash" size={16} /> Удалить</button>
          </>
        }
      />

      {doc.status === "failed" ? <Callout tone="danger" title="Индексация не удалась">{doc.error ?? "Неизвестная ошибка"}</Callout> : null}
      {busy ? <Callout tone="info" title="Идёт индексация">Документ разбивается на фрагменты и добавляется в поиск. Страница обновится автоматически.</Callout> : null}
      {error ? <Callout tone="danger" title="Ошибка">{error}</Callout> : null}

      <div className="detail-grid">
        <section className="panel">
          <h3>Свойства</h3>
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              setSaved(null);
              saveMutation.mutate();
            }}
          >
            <label className="field form-grid__wide">
              <span className="field__label">Название</span>
              <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
            </label>
            <label className="field">
              <span className="field__label">Категория</span>
              <select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>
                {Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="field">
              <span className="field__label">Для кого</span>
              <select value={form.audience} onChange={(event) => setForm({ ...form, audience: event.target.value })}>
                {Object.entries(audiences).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="field form-grid__wide">
              <span className="field__label">Описание</span>
              <textarea rows={3} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </label>
            <div className="form-grid__wide row">
              <button type="submit" className="primary" disabled={saveMutation.isPending}>Сохранить</button>
              {saved ? <span className="success">{saved}</span> : null}
            </div>
          </form>
        </section>

        <section className="panel">
          <h3>Индекс</h3>
          <dl className="kv">
            <dt>Фрагментов</dt><dd>{doc.status === "ingested" ? formatNumber(doc.chunks) : "—"}</dd>
            <dt>Страниц</dt><dd>{doc.metadata?.pages ? String(doc.metadata.pages) : "—"}</dd>
            <dt>Символов</dt><dd>{doc.metadata?.characters ? formatNumber(Number(doc.metadata.characters)) : "—"}</dd>
            <dt>Проиндексирован</dt><dd>{formatDate(doc.indexed_at)}</dd>
            <dt>ID документа</dt><dd><code>{doc.document_id}</code></dd>
          </dl>
        </section>
      </div>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h3>Фрагменты</h3>
            <p className="muted">Так документ видят агенты: каждый фрагмент ищется отдельно.</p>
          </div>
          <label className="toolbar__search">
            <Icon name="search" size={16} />
            <input type="search" value={chunkFilter} onChange={(event) => setChunkFilter(event.target.value)} placeholder="Найти в тексте" />
          </label>
        </div>
        {doc.status !== "ingested" ? (
          <EmptyState icon="layers" title="Фрагментов пока нет" text="Они появятся после успешной индексации." />
        ) : chunksQuery.isLoading ? (
          <div className="skeleton-list">{[0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 90 }} />)}</div>
        ) : !chunks.length ? (
          <EmptyState icon="search" title="Совпадений нет" />
        ) : (
          <ol className="chunk-list">
            {chunks.map((chunk) => {
              const meta = chunk.metadata as Record<string, string | number | undefined>;
              return (
                <li key={chunk.id} className="chunk">
                  <div className="chunk__meta">
                    <span className="chunk__index">#{meta.chunk_index}</span>
                    {meta.page ? <span>стр. {meta.page}{meta.page_end && meta.page_end !== meta.page ? `–${meta.page_end}` : ""}</span> : null}
                    {meta.section ? <span className="chunk__section">{String(meta.section)}</span> : null}
                    <span className="chunk__chars">{formatNumber(chunk.content.length)} симв.</span>
                  </div>
                  <p>{chunk.content}</p>
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </div>
  );
}
