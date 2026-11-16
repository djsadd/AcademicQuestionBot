import { useEffect, useMemo, useState, type ReactNode } from "react";
import { NavLink, Navigate, useLocation } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAdmissionInfo, fetchAdmissionPrograms, updateAdmissionInfo } from "../api/admin";
import type { AdmissionInfoPayload, AdmissionProgram, AdmissionTechnicalContact } from "../types";
import { formatNumber } from "../utils/format";
import { AdmissionApplications } from "./AdmissionApplications";
import { Callout, Drawer, EmptyState, LoadingRows, PageHeader, Pagination } from "./ui/Admin";
import { Icon, type IconName } from "./ui/Icon";

const LEVEL_OPTIONS = [
  { value: "bachelor", label: "Бакалавриат" },
  { value: "master", label: "Магистратура" },
  { value: "doctorate", label: "Докторантура" },
  { value: "second_higher", label: "Второе высшее" },
] as const;
const LEVEL_LABELS: Record<string, string> = Object.fromEntries(LEVEL_OPTIONS.map((item) => [item.value, item.label]));

const SECTIONS: { key: string; label: string; icon: IconName }[] = [
  { key: "programs", label: "Программы", icon: "cap" },
  { key: "contacts", label: "Контакты", icon: "phone" },
  { key: "general", label: "Общее", icon: "settings" },
  { key: "scholarships", label: "Стипендии", icon: "wallet" },
  { key: "documents", label: "Документы", icon: "file" },
  { key: "durations", label: "Сроки обучения", icon: "clock" },
  { key: "foreign-admission", label: "Иностранцы", icon: "link" },
  { key: "management", label: "Руководство", icon: "users" },
  { key: "applications", label: "Заявки", icon: "layers" },
];

type JsonKey = "scholarships" | "management" | "foreign_admission" | "duration_rules" | "documents";
const JSON_SECTIONS: Record<string, { key: JsonKey; title: string; description: string }> = {
  scholarships: { key: "scholarships", title: "Стипендии и гранты", description: "Государственные гранты, скидки и стипендии, о которых рассказывает агент." },
  management: { key: "management", title: "Руководство", description: "Ректорат и руководители подразделений." },
  "foreign-admission": { key: "foreign_admission", title: "Приём иностранных граждан", description: "Правила и документы для иностранных абитуриентов." },
  durations: { key: "duration_rules", title: "Сроки обучения", description: "Правила расчёта длительности обучения по уровням и базам." },
  documents: { key: "documents", title: "Документы для поступления", description: "Списки документов по уровням обучения." },
};
const JSON_KEYS: JsonKey[] = ["scholarships", "management", "foreign_admission", "duration_rules", "documents"];

const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const linesToArray = (value: string) => value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
const arrayToLines = (value?: string[]) => (value ?? []).join("\n");
const asText = (value: unknown) => (typeof value === "string" ? value : value == null ? "" : JSON.stringify(value));
const toNumber = (value: string) => (value === "" ? null : Number(value));

function emptyProgram(): AdmissionProgram {
  return {
    id: "", name: "", name_ru: "", name_kk: "", name_en: "", profile_subject_1: "", profile_subject_2: "",
    aliases: [], level: "bachelor", duration: "", tuition: { amount: null, period: "" },
    passing_score: { gop_code: "", grant: null, grant_full: null, grant_short: null, paid: null, exam: "", notes: [] },
    source: "",
  };
}

function parseJsonObject(label: string, value: string): Record<string, unknown> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch (error) {
    throw new Error(`${label}: ${(error as Error).message}`);
  }
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error(`${label}: должен быть JSON-объектом.`);
  return parsed as Record<string, unknown>;
}

function Field({ label, hint, wide, children }: { label: string; hint?: string; wide?: boolean; children: ReactNode }) {
  return (
    <label className={`field${wide ? " form-grid__wide" : ""}`}>
      <span className="field__label">{label}</span>
      {children}
      {hint ? <span className="field__hint">{hint}</span> : null}
    </label>
  );
}

/* ------------------------------------------------------------ program */
function ProgramForm({ program, onChange }: { program: AdmissionProgram; onChange: (next: AdmissionProgram) => void }) {
  const set = (patch: Partial<AdmissionProgram>) => onChange({ ...program, ...patch });
  const setTuition = (patch: Partial<AdmissionProgram["tuition"]>) => set({ tuition: { ...program.tuition, ...patch } });
  const setScore = (patch: Partial<AdmissionProgram["passing_score"]>) => set({ passing_score: { ...program.passing_score, ...patch } });

  return (
    <div className="stack-lg">
      <section className="form-section">
        <h4>Основное</h4>
        <div className="form-grid">
          <Field label="Название" wide><input value={program.name} onChange={(e) => set({ name: e.target.value })} /></Field>
          <Field label="Уровень">
            <select value={program.level} onChange={(e) => set({ level: e.target.value })}>
              {LEVEL_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </Field>
          <Field label="ID"><input value={program.id ?? ""} onChange={(e) => set({ id: e.target.value })} /></Field>
          <Field label="Название (RU)"><input value={program.name_ru ?? ""} onChange={(e) => set({ name_ru: e.target.value })} /></Field>
          <Field label="Название (KK)"><input value={program.name_kk ?? ""} onChange={(e) => set({ name_kk: e.target.value })} /></Field>
          <Field label="Название (EN)"><input value={program.name_en ?? ""} onChange={(e) => set({ name_en: e.target.value })} /></Field>
          <Field label="Источник (URL)"><input value={program.source ?? ""} onChange={(e) => set({ source: e.target.value })} placeholder="https://" /></Field>
          <Field label="Синонимы" hint="По одному на строку — так абитуриенты могут называть программу" wide>
            <textarea rows={3} value={arrayToLines(program.aliases)} onChange={(e) => set({ aliases: linesToArray(e.target.value) })} />
          </Field>
        </div>
      </section>

      <section className="form-section">
        <h4>Стоимость и сроки</h4>
        <div className="form-grid">
          <Field label="Стоимость, ₸"><input type="number" value={program.tuition.amount ?? ""} onChange={(e) => setTuition({ amount: toNumber(e.target.value) })} /></Field>
          <Field label="Период оплаты"><input value={asText(program.tuition.period)} onChange={(e) => setTuition({ period: e.target.value })} placeholder="в год" /></Field>
          <Field label="Длительность обучения" wide><input value={asText(program.duration)} onChange={(e) => set({ duration: e.target.value })} placeholder="4 года" /></Field>
        </div>
      </section>

      <section className="form-section">
        <h4>Поступление</h4>
        <div className="form-grid form-grid--3">
          <Field label="Профильный предмет 1"><input value={program.profile_subject_1 ?? ""} onChange={(e) => set({ profile_subject_1: e.target.value })} /></Field>
          <Field label="Профильный предмет 2"><input value={program.profile_subject_2 ?? ""} onChange={(e) => set({ profile_subject_2: e.target.value })} /></Field>
          <Field label="Код ГОП"><input value={program.passing_score.gop_code ?? ""} onChange={(e) => setScore({ gop_code: e.target.value })} /></Field>
          <Field label="Грант"><input type="number" value={program.passing_score.grant ?? ""} onChange={(e) => setScore({ grant: toNumber(e.target.value) })} /></Field>
          <Field label="Грант (полный курс)"><input type="number" value={program.passing_score.grant_full ?? ""} onChange={(e) => setScore({ grant_full: toNumber(e.target.value) })} /></Field>
          <Field label="Грант (сокращённый)"><input type="number" value={program.passing_score.grant_short ?? ""} onChange={(e) => setScore({ grant_short: toNumber(e.target.value) })} /></Field>
          <Field label="Платное обучение"><input type="number" value={program.passing_score.paid ?? ""} onChange={(e) => setScore({ paid: toNumber(e.target.value) })} /></Field>
          <Field label="Экзамен"><input value={asText(program.passing_score.exam)} onChange={(e) => setScore({ exam: e.target.value })} /></Field>
          <Field label="Примечания к баллам" hint="По одному на строку" wide>
            <textarea rows={3} value={arrayToLines(program.passing_score.notes)} onChange={(e) => setScore({ notes: linesToArray(e.target.value) })} />
          </Field>
        </div>
      </section>
    </div>
  );
}

function ProgramsSection({ programs, onChange }: { programs: AdmissionProgram[]; onChange: (programs: AdmissionProgram[]) => void }) {
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [editing, setEditing] = useState<number | null>(null);

  useEffect(() => setPage(1), [search, level, pageSize]);

  // Filtering happens on the server (it knows aliases / translations); rows map back by index.
  const query = useQuery({
    queryKey: ["admission-programs", page, pageSize, level, search],
    queryFn: () => fetchAdmissionPrograms(page, pageSize, level, search),
    placeholderData: (previous) => previous,
  });
  const rows = useMemo(
    () => (query.data?.items ?? []).map(({ program_index }) => ({ index: program_index, program: programs[program_index] })).filter((row) => row.program),
    [programs, query.data],
  );
  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    for (const program of programs) result[program.level] = (result[program.level] ?? 0) + 1;
    return result;
  }, [programs]);

  const update = (index: number, next: AdmissionProgram) => onChange(programs.map((item, i) => (i === index ? next : item)));
  const remove = (index: number) => {
    const program = programs[index];
    if (window.confirm(`Удалить программу «${program?.name || "без названия"}»?`)) {
      onChange(programs.filter((_, i) => i !== index));
      setEditing(null);
    }
  };

  return (
    <section className="panel">
      <div className="panel__head">
        <div>
          <h3>Образовательные программы</h3>
          <p className="muted">Цены, проходные баллы и профильные предметы, которые агент называет абитуриентам.</p>
        </div>
        <button type="button" className="primary" onClick={() => { onChange([...programs, emptyProgram()]); setEditing(programs.length); }}>
          <Icon name="plus" size={16} /> Добавить программу
        </button>
      </div>

      <div className="toolbar">
        <label className="toolbar__search">
          <Icon name="search" size={16} />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Название, ID, синоним, код ГОП" />
        </label>
        <div className="segmented" role="group" aria-label="Уровень">
          <button type="button" className={level === "all" ? "is-active" : undefined} onClick={() => setLevel("all")}>Все · {programs.length}</button>
          {LEVEL_OPTIONS.filter((option) => counts[option.value]).map((option) => (
            <button key={option.value} type="button" className={level === option.value ? "is-active" : undefined} onClick={() => setLevel(option.value)}>
              {option.label} · {counts[option.value]}
            </button>
          ))}
        </div>
      </div>

      {query.isLoading ? (
        <LoadingRows rows={5} />
      ) : query.isError ? (
        <Callout tone="danger" title="Не удалось загрузить программы">{(query.error as Error).message}</Callout>
      ) : !rows.length ? (
        <EmptyState icon="cap" title="Программы не найдены" text="Измените фильтр или добавьте программу." />
      ) : (
        <>
          <div className="table-wrapper">
            <table className="click-table">
              <thead>
                <tr>
                  <th>Программа</th>
                  <th>Уровень</th>
                  <th className="num">Стоимость</th>
                  <th className="num">Проходной балл</th>
                  <th aria-label="Действия" />
                </tr>
              </thead>
              <tbody>
                {rows.map(({ program, index }) => {
                  const score = program.passing_score.grant_full ?? program.passing_score.grant ?? program.passing_score.paid;
                  return (
                    <tr key={`${program.id}-${index}`} onClick={() => setEditing(index)}>
                      <td>
                        <strong>{program.name || "Без названия"}</strong>
                        <div className="muted cell-sub">
                          {[program.passing_score.gop_code, program.profile_subject_1 && `${program.profile_subject_1} + ${program.profile_subject_2 || "—"}`].filter(Boolean).join(" · ") || "—"}
                        </div>
                      </td>
                      <td><span className="tag">{LEVEL_LABELS[program.level] ?? program.level}</span></td>
                      <td className="num nowrap">
                        {program.tuition.amount != null ? `${formatNumber(program.tuition.amount)} ₸` : "—"}
                        {program.tuition.period ? <div className="muted cell-sub">{asText(program.tuition.period)}</div> : null}
                      </td>
                      <td className="num">{score != null ? formatNumber(score) : "—"}</td>
                      <td>
                        <div className="row-actions">
                          <button type="button" className="icon-button" aria-label="Изменить" onClick={(e) => { e.stopPropagation(); setEditing(index); }}><Icon name="edit" size={16} /></button>
                          <button type="button" className="icon-button icon-button--danger" aria-label="Удалить" onClick={(e) => { e.stopPropagation(); remove(index); }}><Icon name="trash" size={16} /></button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination page={page} pages={query.data?.pages} onChange={setPage} total={query.data?.total} perPage={pageSize} perPageOptions={[10, 20, 50]} onPerPageChange={setPageSize} />
        </>
      )}

      {editing !== null && programs[editing] ? (
        <Drawer title={programs[editing].name || "Новая программа"} subtitle="Изменения применятся после нажатия «Сохранить» внизу страницы" onClose={() => setEditing(null)} width={760}>
          <ProgramForm program={programs[editing]} onChange={(next) => update(editing, next)} />
          <div className="drawer__foot">
            <button type="button" className="ghost btn--danger" onClick={() => remove(editing)}><Icon name="trash" size={16} /> Удалить</button>
            <button type="button" className="primary" onClick={() => setEditing(null)}>Готово</button>
          </div>
        </Drawer>
      ) : null}
    </section>
  );
}

/* ----------------------------------------------------------- contacts */
function ContactsSection({ contacts, onChange }: { contacts: AdmissionInfoPayload["contacts"]; onChange: (patch: Partial<AdmissionInfoPayload["contacts"]>) => void }) {
  const technical: AdmissionTechnicalContact[] = contacts.technical_contacts ?? [];
  const setTechnical = (next: AdmissionTechnicalContact[]) => onChange({ technical_contacts: next });
  return (
    <>
      <section className="panel">
        <h3>Приёмная комиссия</h3>
        <div className="form-grid">
          <Field label="Отдел"><input value={contacts.department ?? ""} onChange={(e) => onChange({ department: e.target.value })} /></Field>
          <Field label="Сайт"><input value={asText(contacts.website)} onChange={(e) => onChange({ website: e.target.value })} placeholder="https://" /></Field>
          <Field label="Адрес" wide><textarea rows={2} value={contacts.address ?? ""} onChange={(e) => onChange({ address: e.target.value })} /></Field>
          <Field label="Часы работы" wide><input value={contacts.working_hours ?? ""} onChange={(e) => onChange({ working_hours: e.target.value })} placeholder="Пн–Пт 9:00–18:00" /></Field>
          <Field label="Телефоны" hint="По одному на строку"><textarea rows={3} value={arrayToLines(contacts.phone)} onChange={(e) => onChange({ phone: linesToArray(e.target.value) })} /></Field>
          <Field label="Email" hint="По одному на строку"><textarea rows={3} value={arrayToLines(contacts.email)} onChange={(e) => onChange({ email: linesToArray(e.target.value) })} /></Field>
        </div>
      </section>

      <section className="panel">
        <div className="panel__head">
          <div>
            <h3>Технические контакты</h3>
            <p className="muted">Кому звонить по проблемам с подачей документов и личным кабинетом.</p>
          </div>
          <button type="button" className="ghost" onClick={() => setTechnical([...technical, { name: "", phone: "", note: "" }])}>
            <Icon name="plus" size={16} /> Добавить
          </button>
        </div>
        {!technical.length ? (
          <EmptyState icon="phone" title="Нет технических контактов" />
        ) : (
          <div className="stack">
            {technical.map((contact, index) => (
              <div key={index} className="contact-row">
                <input value={contact.name} onChange={(e) => setTechnical(technical.map((c, i) => (i === index ? { ...c, name: e.target.value } : c)))} placeholder="Имя" aria-label="Имя" />
                <input value={contact.phone} onChange={(e) => setTechnical(technical.map((c, i) => (i === index ? { ...c, phone: e.target.value } : c)))} placeholder="Телефон" aria-label="Телефон" />
                <input value={contact.note ?? ""} onChange={(e) => setTechnical(technical.map((c, i) => (i === index ? { ...c, note: e.target.value } : c)))} placeholder="Примечание" aria-label="Примечание" />
                <button type="button" className="icon-button icon-button--danger" aria-label="Удалить" onClick={() => setTechnical(technical.filter((_, i) => i !== index))}><Icon name="trash" size={16} /></button>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function JsonEditor({ title, description, value, onChange }: { title: string; description: string; value: string; onChange: (value: string) => void }) {
  const error = useMemo(() => {
    try {
      parseJsonObject(title, value);
      return null;
    } catch (err) {
      return (err as Error).message;
    }
  }, [title, value]);
  const format = () => {
    try {
      onChange(JSON.stringify(JSON.parse(value), null, 2));
    } catch {
      // keep invalid text as is
    }
  };
  return (
    <section className="panel">
      <div className="panel__head">
        <div>
          <h3>{title}</h3>
          <p className="muted">{description}</p>
        </div>
        <div className="row">
          <span className={`tag ${error ? "tag--danger" : "tag--success"}`}><Icon name={error ? "alert" : "check"} size={12} /> {error ? "Ошибка JSON" : "JSON корректен"}</span>
          <button type="button" className="ghost btn--sm" onClick={format} disabled={Boolean(error)}>Форматировать</button>
        </div>
      </div>
      <textarea className={`code-editor${error ? " is-invalid" : ""}`} spellCheck={false} rows={22} value={value} onChange={(e) => onChange(e.target.value)} aria-label={title} />
      {error ? <span className="error field__hint">{error}</span> : null}
    </section>
  );
}

/* ---------------------------------------------------------------- page */
function AdmissionInfoEditor({ section }: { section: string }) {
  const queryClient = useQueryClient();
  const infoQuery = useQuery({ queryKey: ["admission-info"], queryFn: fetchAdmissionInfo });
  const [form, setForm] = useState<AdmissionInfoPayload | null>(null);
  const [jsonTexts, setJsonTexts] = useState<Record<JsonKey, string>>({} as Record<JsonKey, string>);
  const [message, setMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);

  const load = (payload: AdmissionInfoPayload) => {
    setForm(clone(payload));
    setJsonTexts(Object.fromEntries(JSON_KEYS.map((key) => [key, JSON.stringify(payload[key] ?? {}, null, 2)])) as Record<JsonKey, string>);
  };

  useEffect(() => {
    if (infoQuery.data?.data) load(infoQuery.data.data);
  }, [infoQuery.data]);

  const original = infoQuery.data?.data;
  const dirty = useMemo(() => {
    if (!form || !original) return false;
    const { scholarships: _s, management: _m, foreign_admission: _f, duration_rules: _d, documents: _doc, ...rest } = form;
    const { scholarships: _s2, management: _m2, foreign_admission: _f2, duration_rules: _d2, documents: _doc2, ...restOriginal } = original;
    if (JSON.stringify(rest) !== JSON.stringify(restOriginal)) return true;
    return JSON_KEYS.some((key) => jsonTexts[key] !== JSON.stringify(original[key] ?? {}, null, 2));
  }, [form, original, jsonTexts]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const save = useMutation({
    mutationFn: updateAdmissionInfo,
    onSuccess: (response) => {
      queryClient.setQueryData(["admission-info"], response);
      queryClient.invalidateQueries({ queryKey: ["admission-programs"] });
      setMessage({ tone: "success", text: "Изменения сохранены. Агент уже использует новые данные." });
    },
    onError: (error) => setMessage({ tone: "danger", text: error instanceof Error ? error.message : "Не удалось сохранить." }),
  });

  if (infoQuery.isLoading || (!form && !infoQuery.isError)) return <LoadingRows rows={4} height={80} />;
  if (infoQuery.isError || !form) return <Callout tone="danger" title="Не удалось загрузить данные приёмной комиссии">{(infoQuery.error as Error | null)?.message}</Callout>;

  const handleSave = () => {
    try {
      const jsonBlocks = Object.fromEntries(
        JSON_KEYS.map((key) => [key, parseJsonObject(Object.values(JSON_SECTIONS).find((s) => s.key === key)?.title ?? key, jsonTexts[key])]),
      );
      const payload: AdmissionInfoPayload = {
        ...form,
        ...jsonBlocks,
        contacts: {
          ...form.contacts,
          phone: form.contacts.phone ?? [],
          email: form.contacts.email ?? [],
          technical_contacts: (form.contacts.technical_contacts ?? [])
            .map((contact) => ({ ...contact, name: contact.name.trim(), phone: contact.phone.trim(), note: (contact.note ?? "").trim() }))
            .filter((contact) => contact.name || contact.phone),
        },
        programs: form.programs.map((program) => ({
          ...program,
          name: program.name.trim(),
          id: (program.id ?? "").trim(),
          name_ru: (program.name_ru ?? "").trim(),
          name_kk: (program.name_kk ?? "").trim(),
          name_en: (program.name_en ?? "").trim(),
          profile_subject_1: (program.profile_subject_1 ?? "").trim(),
          profile_subject_2: (program.profile_subject_2 ?? "").trim(),
          source: (program.source ?? "").trim(),
          aliases: (program.aliases ?? []).map((item) => item.trim()).filter(Boolean),
          duration: typeof program.duration === "string" ? program.duration.trim() : program.duration,
          tuition: { ...program.tuition, period: typeof program.tuition.period === "string" ? program.tuition.period.trim() : program.tuition.period },
          passing_score: {
            ...program.passing_score,
            exam: typeof program.passing_score.exam === "string" ? program.passing_score.exam.trim() : program.passing_score.exam,
            notes: (program.passing_score.notes ?? []).map((item) => item.trim()).filter(Boolean),
          },
        })),
      };
      setMessage(null);
      save.mutate(payload);
    } catch (error) {
      setMessage({ tone: "danger", text: (error as Error).message });
    }
  };

  const reset = () => {
    if (original && window.confirm("Отменить все несохранённые изменения?")) {
      load(original);
      setMessage(null);
    }
  };

  const jsonSection = JSON_SECTIONS[section];
  let content: ReactNode;
  if (section === "programs") {
    content = <ProgramsSection programs={form.programs} onChange={(programs) => setForm({ ...form, programs })} />;
  } else if (section === "contacts") {
    content = <ContactsSection contacts={form.contacts} onChange={(patch) => setForm({ ...form, contacts: { ...form.contacts, ...patch } })} />;
  } else if (section === "applications") {
    content = <AdmissionApplications />;
  } else if (jsonSection) {
    content = (
      <JsonEditor
        title={jsonSection.title}
        description={jsonSection.description}
        value={jsonTexts[jsonSection.key] ?? "{}"}
        onChange={(value) => setJsonTexts({ ...jsonTexts, [jsonSection.key]: value })}
      />
    );
  } else {
    content = (
      <section className="panel">
        <h3>Общие данные</h3>
        <div className="form-grid">
          <Field label="Учреждение" wide><input value={form.institution} onChange={(e) => setForm({ ...form, institution: e.target.value })} /></Field>
          <Field label="Валюта"><input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} /></Field>
          <Field label="Последнее обновление" hint="Заполняется автоматически при сохранении"><input value={form.last_updated ?? ""} readOnly /></Field>
        </div>
        <p className="muted field__hint">Файл данных: <code>{infoQuery.data?.source_path}</code></p>
      </section>
    );
  }

  return (
    <div className="stack-lg">
      <PageHeader
        eyebrow="База знаний"
        title="Приёмная комиссия"
        description={<>Структурированные данные, по которым агент отвечает абитуриентам: {formatNumber(form.programs.length)} программ, контакты, документы и гранты.</>}
      />

      <nav className="subnav" aria-label="Разделы">
        {SECTIONS.map((item) => (
          <NavLink key={item.key} to={`/admissions/${item.key}`} className={({ isActive }) => `subnav__item${isActive ? " is-active" : ""}`}>
            <Icon name={item.icon} size={15} /> {item.label}
          </NavLink>
        ))}
      </nav>

      {message ? (
        <Callout tone={message.tone} title={message.tone === "success" ? "Готово" : "Ошибка"} action={<button type="button" className="ghost btn--sm" onClick={() => setMessage(null)}>Скрыть</button>}>
          {message.text}
        </Callout>
      ) : null}

      {content}

      {dirty && section !== "applications" ? (
        <div className="save-bar" role="status">
          <span><span className="status-dot status-dot--warning" /> Есть несохранённые изменения</span>
          <div className="row">
            <button type="button" className="ghost" onClick={reset} disabled={save.isPending}>Отменить</button>
            <button type="button" className="primary" onClick={handleSave} disabled={save.isPending}>
              {save.isPending ? <span className="spinner spinner--on-brand" /> : <Icon name="check" size={16} />} Сохранить
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function AdmissionsAdmin() {
  const location = useLocation();
  const segment = location.pathname.replace(/\/+$/, "").split("/")[2];
  if (!segment) return <Navigate to="/admissions/programs" replace />;
  if (!SECTIONS.some((item) => item.key === segment)) return <Navigate to="/admissions/programs" replace />;
  return <AdmissionInfoEditor section={segment} />;
}
