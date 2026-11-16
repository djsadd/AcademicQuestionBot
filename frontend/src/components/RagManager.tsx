import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, downloadDocument, fetchDocuments, fetchStats, reindexAll, reindexDocument } from "../api/rag";
import type { RagDocument } from "../types";
import { formatBytes, formatNumber, formatRelative, pluralize } from "../utils/format";
import { SearchPlayground } from "./rag/SearchPlayground";
import { UploadPanel } from "./rag/UploadPanel";
import { Callout, EmptyState, PageHeader, StatCard, StatusBadge, Tabs } from "./ui/Admin";
import { Icon } from "./ui/Icon";

type Tab = "documents" | "search";
const ACTIVE = new Set(["queued", "processing"]);
const STALE_MS = 10 * 60 * 1000;

// A job stuck in the queue (worker restarted, broker lost the message) can be retried.
const isStale = (doc: RagDocument) =>
  ACTIVE.has(doc.status ?? "") && Date.now() - new Date(doc.updated_at ?? doc.uploaded_at).getTime() > STALE_MS;

export function RagManager() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("documents");
  const [showUpload, setShowUpload] = useState(false);
  const [filter, setFilter] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);

  const statsQuery = useQuery({ queryKey: ["rag-stats"], queryFn: fetchStats, refetchInterval: 15_000 });
  const documentsQuery = useQuery({
    queryKey: ["rag-documents"],
    queryFn: fetchDocuments,
    // Poll only while something is being indexed.
    refetchInterval: (query) => ((query.state.data ?? []).some((doc) => ACTIVE.has(doc.status ?? "")) ? 2500 : false),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["rag-documents"] });
    queryClient.invalidateQueries({ queryKey: ["rag-stats"] });
  };
  const onError = (error: unknown) => setActionError(error instanceof Error ? error.message : "Действие не выполнено.");

  const deleteMutation = useMutation({ mutationFn: deleteDocument, onSuccess: refresh, onError });
  const reindexMutation = useMutation({ mutationFn: reindexDocument, onSuccess: refresh, onError });
  const reindexAllMutation = useMutation({ mutationFn: (recreate: boolean) => reindexAll(recreate), onSuccess: refresh, onError });

  const stats = statsQuery.data;
  const categories = stats?.categories ?? {};
  const documents = useMemo(() => documentsQuery.data ?? [], [documentsQuery.data]);
  const filtered = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return documents.filter((doc) => {
      if (category && doc.category !== category) return false;
      if (status && doc.status !== status) return false;
      if (!needle) return true;
      return [doc.title, doc.original_file, doc.metadata?.description].some((value) => String(value ?? "").toLowerCase().includes(needle));
    });
  }, [documents, filter, category, status]);

  const byStatus = stats?.registry.by_status ?? {};
  const inProgress = (byStatus.queued ?? 0) + (byStatus.processing ?? 0);
  const failed = byStatus.failed ?? 0;
  const index = stats?.index;

  const confirmDelete = (doc: RagDocument) => {
    if (window.confirm(`Удалить «${doc.title ?? doc.original_file}»? Документ исчезнет из поиска агентов.`)) {
      deleteMutation.mutate(doc.document_id);
    }
  };

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="RAG"
        title="База знаний"
        description="Документы, на которые опираются ИИ-агенты: регламенты, приказы, учебные планы и инструкции. Всё, что загружено сюда, попадает в поиск ассистента."
        actions={
          <>
            <button
              type="button"
              className="ghost"
              disabled={reindexAllMutation.isPending || !documents.length}
              onClick={() => window.confirm("Переиндексировать все документы? Это займёт время и потратит запросы к API эмбеддингов.") && reindexAllMutation.mutate(false)}
            >
              <Icon name="refresh" size={16} /> Переиндексировать всё
            </button>
            <button type="button" className="primary" onClick={() => { setShowUpload(true); setTab("documents"); }}>
              <Icon name="upload" size={16} /> Загрузить
            </button>
          </>
        }
      />

      {index?.dimension_mismatch ? (
        <Callout
          tone="danger"
          title="Индекс несовместим с моделью эмбеддингов"
          action={
            <button
              type="button"
              className="primary btn--sm"
              disabled={reindexAllMutation.isPending}
              onClick={() => window.confirm("Пересоздать коллекцию и заново проиндексировать все документы?") && reindexAllMutation.mutate(true)}
            >
              Пересоздать индекс
            </button>
          }
        >
          Коллекция «{index.collection}» хранит векторы размерности {index.vector_size}, а модель «{index.embeddings.model}» выдаёт {index.configured_vector_size}. Поиск по документам сейчас не работает.
        </Callout>
      ) : null}
      {index?.error && !index.dimension_mismatch ? <Callout tone="danger" title="Векторное хранилище недоступно">{index.error}</Callout> : null}
      {index && !index.embeddings.remote ? (
        <Callout tone="warning" title="Не настроен API эмбеддингов">
          Без OPENAI_API_KEY используются упрощённые локальные векторы — качество поиска будет низким.
        </Callout>
      ) : null}
      {actionError ? <Callout tone="danger" title="Ошибка" action={<button type="button" className="ghost btn--sm" onClick={() => setActionError(null)}>Скрыть</button>}>{actionError}</Callout> : null}

      <div className="stat-grid">
        <StatCard label="Документы" icon="file" value={formatNumber(stats?.registry.documents)} hint={stats ? formatBytes(stats.registry.size_bytes) : undefined} />
        <StatCard label="Фрагменты в индексе" icon="database" value={formatNumber(index?.points ?? stats?.registry.chunks)} hint={index ? `${index.mode === "qdrant" ? "Qdrant" : index.mode} · ${index.embeddings.model}` : undefined} />
        <StatCard label="В обработке" icon="clock" tone={inProgress ? "warning" : undefined} value={formatNumber(inProgress)} hint={inProgress ? "обновляется автоматически" : "очередь пуста"} />
        <StatCard label="С ошибками" icon="alert" tone={failed ? "danger" : "success"} value={formatNumber(failed)} hint={failed ? "нажмите «Повторить» в строке" : "всё проиндексировано"} />
      </div>

      {showUpload ? <UploadPanel stats={stats} onClose={() => setShowUpload(false)} /> : null}

      <Tabs<Tab>
        value={tab}
        onChange={setTab}
        items={[
          { value: "documents", label: "Документы", count: documents.length, icon: "file" },
          { value: "search", label: "Проверка поиска", icon: "search" },
        ]}
      />

      {tab === "search" ? (
        <SearchPlayground />
      ) : (
        <section className="panel">
          <div className="toolbar">
            <label className="toolbar__search">
              <Icon name="search" size={16} />
              <input type="search" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Поиск по названию" />
            </label>
            <select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Категория">
              <option value="">Все категории</option>
              {Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Статус">
              <option value="">Все статусы</option>
              <option value="ingested">Готов</option>
              <option value="processing">Индексация</option>
              <option value="queued">В очереди</option>
              <option value="failed">Ошибка</option>
            </select>
          </div>

          {documentsQuery.isLoading ? (
            <div className="skeleton-list">{[0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 56 }} />)}</div>
          ) : documentsQuery.isError ? (
            <Callout tone="danger" title="Не удалось загрузить документы">{(documentsQuery.error as Error).message}</Callout>
          ) : !documents.length ? (
            <EmptyState
              icon="database"
              title="База знаний пуста"
              text="Загрузите регламенты и положения университета — агенты начнут отвечать по ним."
              action={<button type="button" className="primary" onClick={() => setShowUpload(true)}><Icon name="upload" size={16} /> Загрузить первый документ</button>}
            />
          ) : !filtered.length ? (
            <EmptyState icon="filter" title="Ничего не найдено" text="Измените фильтры." />
          ) : (
            <div className="table-wrapper">
              <table className="doc-table">
                <thead>
                  <tr>
                    <th>Документ</th>
                    <th>Категория</th>
                    <th>Статус</th>
                    <th className="num">Фрагменты</th>
                    <th>Обновлён</th>
                    <th aria-label="Действия" />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((doc) => (
                    <tr key={doc.document_id}>
                      <td>
                        <Link to={`/rag/${doc.document_id}`} className="doc-cell">
                          <span className="doc-cell__icon">{(doc.original_file.split(".").pop() ?? "").toUpperCase().slice(0, 4)}</span>
                          <span className="doc-cell__text">
                            <strong>{doc.title ?? doc.original_file}</strong>
                            <span>
                              {doc.original_file} · {formatBytes(doc.size_bytes)}
                              {doc.metadata?.pages ? ` · ${doc.metadata.pages} ${pluralize(Number(doc.metadata.pages), ["стр.", "стр.", "стр."])}` : ""}
                            </span>
                          </span>
                        </Link>
                      </td>
                      <td>
                        <span className="tag">{categories[doc.category ?? ""] ?? "—"}</span>
                        {doc.audience && doc.audience !== "all" ? <span className="tag tag--muted">{stats?.audiences[doc.audience] ?? doc.audience}</span> : null}
                      </td>
                      <td>
                        <StatusBadge status={doc.status} />
                        {doc.status === "failed" && doc.error ? <div className="cell-error" title={doc.error}>{doc.error}</div> : null}
                      </td>
                      <td className="num">{doc.status === "ingested" ? formatNumber(doc.chunks) : "—"}</td>
                      <td className="nowrap muted">{formatRelative(doc.updated_at ?? doc.uploaded_at)}</td>
                      <td>
                        <div className="row-actions">
                          {doc.status === "failed" || isStale(doc) ? (
                            <button type="button" className="ghost btn--sm" onClick={() => reindexMutation.mutate(doc.document_id)}>
                              <Icon name="refresh" size={14} /> Повторить
                            </button>
                          ) : null}
                          <button type="button" className="icon-button" title="Переиндексировать" aria-label="Переиндексировать" disabled={ACTIVE.has(doc.status ?? "") && !isStale(doc)} onClick={() => reindexMutation.mutate(doc.document_id)}>
                            <Icon name="refresh" size={16} />
                          </button>
                          <button type="button" className="icon-button" title="Скачать" aria-label="Скачать" onClick={() => downloadDocument(doc).catch(onError)}>
                            <Icon name="download" size={16} />
                          </button>
                          <button type="button" className="icon-button icon-button--danger" title="Удалить" aria-label="Удалить" onClick={() => confirmDelete(doc)}>
                            <Icon name="trash" size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
