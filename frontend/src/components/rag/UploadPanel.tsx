import { useRef, useState, type DragEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { uploadDocument } from "../../api/rag";
import type { RagStats } from "../../types";
import { formatBytes } from "../../utils/format";
import { Icon } from "../ui/Icon";

type Item = { id: string; file: File; state: "pending" | "uploading" | "done" | "error" | "duplicate"; message?: string };

export function UploadPanel({ stats, onClose }: { stats?: RagStats; onClose: () => void }) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [dragging, setDragging] = useState(false);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("regulation");
  const [audience, setAudience] = useState("all");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  const extensions = stats?.limits.extensions ?? [".pdf", ".docx", ".txt", ".md"];
  const maxBytes = (stats?.limits.max_upload_mb ?? 50) * 1024 * 1024;

  const addFiles = (files: FileList | File[]) => {
    const next: Item[] = [];
    for (const file of Array.from(files)) {
      const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
      const invalid = !extensions.includes(ext) ? `Формат ${ext} не поддерживается` : file.size > maxBytes ? "Файл слишком большой" : undefined;
      next.push({ id: `${file.name}-${file.size}-${file.lastModified}`, file, state: invalid ? "error" : "pending", message: invalid });
    }
    setItems((current) => [...current, ...next.filter((item) => !current.some((c) => c.id === item.id))]);
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length) addFiles(event.dataTransfer.files);
  };

  const patch = (id: string, data: Partial<Item>) => setItems((current) => current.map((item) => (item.id === id ? { ...item, ...data } : item)));

  const upload = async (allowDuplicate = false, only?: string) => {
    setBusy(true);
    const queue = items.filter((item) => (only ? item.id === only : item.state === "pending"));
    for (const item of queue) {
      patch(item.id, { state: "uploading", message: undefined });
      try {
        await uploadDocument(item.file, {
          title: queue.length === 1 && items.length === 1 ? title : undefined,
          category,
          audience,
          description,
          allowDuplicate,
        });
        patch(item.id, { state: "done", message: "Загружен, идёт индексация" });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Ошибка загрузки";
        patch(item.id, { state: message.includes("уже загружен") ? "duplicate" : "error", message });
      }
    }
    setBusy(false);
    queryClient.invalidateQueries({ queryKey: ["rag-documents"] });
    queryClient.invalidateQueries({ queryKey: ["rag-stats"] });
  };

  const pending = items.filter((item) => item.state === "pending").length;
  const single = items.length === 1;

  return (
    <section className="panel upload-panel">
      <div className="upload-panel__head">
        <div>
          <h3>Загрузка документов</h3>
          <p className="muted">PDF, DOCX, TXT или MD до {stats?.limits.max_upload_mb ?? 50} МБ. Можно выбрать несколько файлов.</p>
        </div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Закрыть">
          <Icon name="x" />
        </button>
      </div>

      <label
        className={`dropzone${dragging ? " is-dragging" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={extensions.join(",")}
          className="sr-only"
          onChange={(event) => {
            if (event.target.files) addFiles(event.target.files);
            event.target.value = "";
          }}
        />
        <span className="dropzone__icon"><Icon name="upload" size={22} /></span>
        <strong>Перетащите файлы сюда</strong>
        <span className="muted">или нажмите, чтобы выбрать</span>
      </label>

      {items.length ? (
        <ul className="upload-list">
          {items.map((item) => (
            <li key={item.id} className={`upload-item is-${item.state}`}>
              <Icon name="file" size={18} />
              <div className="upload-item__text">
                <strong>{item.file.name}</strong>
                <span>{formatBytes(item.file.size)}{item.message ? ` · ${item.message}` : ""}</span>
              </div>
              {item.state === "uploading" ? <span className="spinner" /> : null}
              {item.state === "done" ? <Icon name="check" size={18} className="upload-item__ok" /> : null}
              {item.state === "duplicate" ? (
                <button type="button" className="ghost btn--sm" disabled={busy} onClick={() => upload(true, item.id)}>
                  Загрузить всё равно
                </button>
              ) : null}
              {item.state === "pending" || item.state === "error" || item.state === "duplicate" ? (
                <button type="button" className="icon-button" aria-label="Убрать" onClick={() => setItems((c) => c.filter((x) => x.id !== item.id))}>
                  <Icon name="x" size={16} />
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="form-grid">
        {single ? (
          <label className="field form-grid__wide">
            <span className="field__label">Название</span>
            <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder={items[0]?.file.name.replace(/\.[^.]+$/, "")} />
          </label>
        ) : null}
        <label className="field">
          <span className="field__label">Категория</span>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            {Object.entries(stats?.categories ?? { other: "Другое" }).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Для кого</span>
          <select value={audience} onChange={(event) => setAudience(event.target.value)}>
            {Object.entries(stats?.audiences ?? { all: "Все" }).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="field form-grid__wide">
          <span className="field__label">Описание <span className="muted">(необязательно)</span></span>
          <input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Например: редакция от 2025 года, действует для всех ОП" />
        </label>
      </div>

      <div className="upload-panel__foot">
        <span className="muted">После загрузки документ автоматически разбивается на фрагменты и попадает в поиск агентов.</span>
        <button type="button" className="primary" disabled={!pending || busy} onClick={() => upload()}>
          {busy ? <span className="spinner spinner--on-brand" /> : <Icon name="upload" size={16} />}
          {pending > 1 ? `Загрузить ${pending} файла` : "Загрузить"}
        </button>
      </div>
    </section>
  );
}
