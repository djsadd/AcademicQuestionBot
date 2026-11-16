import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { searchKnowledgeBase } from "../../api/rag";
import { EmptyState } from "../ui/Admin";
import { Icon } from "../ui/Icon";

const EXAMPLES = ["Как проходит пересдача FX?", "Минимальный GPA для стипендии", "Академический отпуск"];

function Highlight({ text, query }: { text: string; query: string }) {
  const stems = query
    .toLowerCase()
    .split(/[^0-9a-zа-яёәіңғүұқөһ]+/i)
    .filter((word) => word.length > 3)
    .map((word) => word.slice(0, Math.max(4, word.length - 2)).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!stems.length) return <>{text}</>;
  // One capture group → split() alternates plain text (even) and matches (odd).
  const parts = text.split(new RegExp(`((?:${stems.join("|")})[0-9a-zа-яёәіңғүұқөһ]*)`, "gi"));
  return <>{parts.map((part, index) => (index % 2 ? <mark key={index}>{part}</mark> : part))}</>;
}

function ScoreBar({ label, value }: { label: string; value?: number }) {
  const percent = Math.max(0, Math.min(100, Math.round((value ?? 0) * 100)));
  return (
    <span className="score-bar" title={`${label}: ${value?.toFixed(3) ?? "—"}`}>
      <span className="score-bar__label">{label}</span>
      <span className="score-bar__track"><span style={{ width: `${percent}%` }} /></span>
      <span className="score-bar__value">{percent}%</span>
    </span>
  );
}

export function SearchPlayground() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [hybrid, setHybrid] = useState(true);
  const search = useMutation({ mutationFn: () => searchKnowledgeBase(query.trim(), topK, hybrid) });

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (query.trim()) search.mutate();
  };

  return (
    <section className="panel">
      <div>
        <h3>Проверка поиска</h3>
        <p className="muted">Покажет ровно те фрагменты, которые получат агенты на такой вопрос. Используйте, чтобы убедиться, что документ «находится».</p>
      </div>
      <form className="search-bar" onSubmit={submit}>
        <Icon name="search" size={18} />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Введите вопрос студента…" aria-label="Поисковый запрос" />
        <select value={topK} onChange={(event) => setTopK(Number(event.target.value))} aria-label="Количество результатов">
          {[3, 5, 8, 10].map((value) => <option key={value} value={value}>Топ {value}</option>)}
        </select>
        <label className="switch">
          <input type="checkbox" checked={hybrid} onChange={(event) => setHybrid(event.target.checked)} />
          <span>Гибридный</span>
        </label>
        <button type="submit" className="primary" disabled={!query.trim() || search.isPending}>
          {search.isPending ? <span className="spinner spinner--on-brand" /> : null}Найти
        </button>
      </form>
      <div className="chip-row">
        {EXAMPLES.map((example) => (
          <button key={example} type="button" className="chip" onClick={() => { setQuery(example); window.setTimeout(() => search.mutate(), 0); }}>
            {example}
          </button>
        ))}
      </div>

      {search.isError ? <p className="error">{(search.error as Error).message}</p> : null}
      {search.data ? (
        search.data.length ? (
          <ol className="search-results">
            {search.data.map((result, index) => {
              const meta = result.metadata as Record<string, string | number | undefined>;
              return (
                <li key={`${meta.document_id}-${meta.chunk_index}-${index}`} className="search-result">
                  <div className="search-result__head">
                    <span className="search-result__rank">{index + 1}</span>
                    <div className="search-result__title">
                      {meta.document_id ? (
                        <Link to={`/rag/${meta.document_id}`}>{String(meta.title ?? meta.original_file ?? meta.file_name ?? "Документ")}</Link>
                      ) : (
                        <strong>{String(meta.title ?? meta.file_name ?? "Документ")}</strong>
                      )}
                      <span className="muted">
                        {[meta.page ? `стр. ${meta.page}` : null, meta.section ? String(meta.section) : null, `фрагмент #${meta.chunk_index ?? "—"}`].filter(Boolean).join(" · ")}
                      </span>
                    </div>
                    <div className="search-result__scores">
                      <ScoreBar label="Итог" value={result.score} />
                      {hybrid ? <ScoreBar label="Смысл" value={result.vector_score} /> : null}
                      {hybrid ? <ScoreBar label="Слова" value={result.keyword_score} /> : null}
                    </div>
                  </div>
                  <p className="search-result__text"><Highlight text={result.content} query={query} /></p>
                </li>
              );
            })}
          </ol>
        ) : (
          <EmptyState icon="search" title="Ничего не найдено" text="Агенты не получат контекста на этот вопрос. Загрузите подходящий документ или переформулируйте запрос." />
        )
      ) : null}
    </section>
  );
}
