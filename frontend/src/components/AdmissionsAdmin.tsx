import { useEffect, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { NavLink, Navigate, useLocation } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAdmissionInfo, updateAdmissionInfo } from "../api/admin";
import { AdmissionApplications } from "./AdmissionApplications";
import type { AdmissionInfoPayload, AdmissionProgram, AdmissionTechnicalContact } from "../types";

const LEVEL_OPTIONS = [
  { value: "bachelor", label: "Бакалавриат" },
  { value: "master", label: "Магистратура" },
  { value: "doctorate", label: "Докторантура" },
  { value: "second_higher", label: "Второе высшее" },
] as const;

const ADMISSION_SECTIONS = [
  { key: "general", label: "Общее" },
  { key: "contacts", label: "Контакты" },
  { key: "programs", label: "Специальности" },
  { key: "durations", label: "Сроки" },
  { key: "documents", label: "Документы" },
  { key: "applications", label: "Заявки" },
] as const;

type AdmissionSectionKey = (typeof ADMISSION_SECTIONS)[number]["key"];

function clonePayload(payload: AdmissionInfoPayload): AdmissionInfoPayload {
  return JSON.parse(JSON.stringify(payload)) as AdmissionInfoPayload;
}

function linesToArray(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function arrayToLines(value: string[] | undefined): string {
  return (value ?? []).join("\n");
}

function parseJsonSection(label: string, value: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
      throw new Error(`${label} должен быть JSON-объектом.`);
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`${label}: ${detail}`);
  }
}

function createEmptyProgram(): AdmissionProgram {
  return {
    id: "",
    name: "",
    name_ru: "",
    name_kk: "",
    name_en: "",
    aliases: [],
    level: "bachelor",
    duration: "",
    tuition: {
      amount: null,
      period: "",
    },
    passing_score: {
      gop_code: "",
      grant_full: null,
      grant_short: null,
      paid: null,
      exam: "",
      notes: [],
    },
  };
}

function createEmptyTechnicalContact(): AdmissionTechnicalContact {
  return {
    name: "",
    phone: "",
    note: "",
  };
}

function ProgramCard({
  program,
  index,
  onChange,
  onRemove,
}: {
  program: AdmissionProgram;
  index: number;
  onChange: (index: number, nextValue: AdmissionProgram) => void;
  onRemove: (index: number) => void;
}) {
  const updateField = (field: keyof AdmissionProgram, value: unknown) => {
    onChange(index, { ...program, [field]: value });
  };

  const updateTuitionField = (field: string, value: unknown) => {
    onChange(index, {
      ...program,
      tuition: {
        ...program.tuition,
        [field]: value,
      },
    });
  };

  const updatePassingField = (field: string, value: unknown) => {
    onChange(index, {
      ...program,
      passing_score: {
        ...program.passing_score,
        [field]: value,
      },
    });
  };

  return (
    <article className="admission-editor__program-card">
      <div className="admission-editor__program-header">
        <div>
          <strong>{program.name || `Программа ${index + 1}`}</strong>
          <p className="muted">Карточка специальности</p>
        </div>
        <button type="button" className="ghost" onClick={() => onRemove(index)}>
          Удалить
        </button>
      </div>

      <div className="admission-editor__grid">
        <label>
          <span>ID</span>
          <input value={program.id ?? ""} onChange={(event) => updateField("id", event.target.value)} />
        </label>
        <label>
          <span>Уровень</span>
          <select value={program.level} onChange={(event) => updateField("level", event.target.value)}>
            {LEVEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Основное название</span>
          <input value={program.name} onChange={(event) => updateField("name", event.target.value)} />
        </label>
        <label>
          <span>Название RU</span>
          <input value={program.name_ru ?? ""} onChange={(event) => updateField("name_ru", event.target.value)} />
        </label>
        <label>
          <span>Название KK</span>
          <input value={program.name_kk ?? ""} onChange={(event) => updateField("name_kk", event.target.value)} />
        </label>
        <label>
          <span>Название EN</span>
          <input value={program.name_en ?? ""} onChange={(event) => updateField("name_en", event.target.value)} />
        </label>
      </div>

      <label>
        <span>Синонимы / aliases, по одному на строку</span>
        <textarea
          rows={4}
          value={arrayToLines(program.aliases)}
          onChange={(event) => updateField("aliases", linesToArray(event.target.value))}
        />
      </label>

      <label>
        <span>Длительность обучения</span>
        <textarea
          rows={3}
          value={typeof program.duration === "string" ? program.duration : JSON.stringify(program.duration, null, 2)}
          onChange={(event) => updateField("duration", event.target.value)}
        />
      </label>

      <div className="admission-editor__grid">
        <label>
          <span>Стоимость</span>
          <input
            type="number"
            value={program.tuition.amount ?? ""}
            onChange={(event) => updateTuitionField("amount", event.target.value === "" ? null : Number(event.target.value))}
          />
        </label>
        <label>
          <span>Период оплаты</span>
          <input
            value={typeof program.tuition.period === "string" ? program.tuition.period : JSON.stringify(program.tuition.period ?? "", null, 2)}
            onChange={(event) => updateTuitionField("period", event.target.value)}
          />
        </label>
        <label>
          <span>ГОП код</span>
          <input
            value={program.passing_score.gop_code ?? ""}
            onChange={(event) => updatePassingField("gop_code", event.target.value)}
          />
        </label>
        <label>
          <span>Экзамен</span>
          <input
            value={typeof program.passing_score.exam === "string" ? program.passing_score.exam : JSON.stringify(program.passing_score.exam ?? "", null, 2)}
            onChange={(event) => updatePassingField("exam", event.target.value)}
          />
        </label>
        <label>
          <span>Грант полный курс</span>
          <input
            type="number"
            value={program.passing_score.grant_full ?? ""}
            onChange={(event) => updatePassingField("grant_full", event.target.value === "" ? null : Number(event.target.value))}
          />
        </label>
        <label>
          <span>Грант сокращенный курс</span>
          <input
            type="number"
            value={program.passing_score.grant_short ?? ""}
            onChange={(event) => updatePassingField("grant_short", event.target.value === "" ? null : Number(event.target.value))}
          />
        </label>
        <label>
          <span>Платное</span>
          <input
            type="number"
            value={program.passing_score.paid ?? ""}
            onChange={(event) => updatePassingField("paid", event.target.value === "" ? null : Number(event.target.value))}
          />
        </label>
      </div>

      <label>
        <span>Примечания к проходным баллам, по одному на строку</span>
        <textarea
          rows={4}
          value={arrayToLines(program.passing_score.notes)}
          onChange={(event) => updatePassingField("notes", linesToArray(event.target.value))}
        />
      </label>
    </article>
  );
}

function TechnicalContactCard({
  contact,
  index,
  onChange,
  onRemove,
}: {
  contact: AdmissionTechnicalContact;
  index: number;
  onChange: (index: number, nextValue: AdmissionTechnicalContact) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <article className="admission-editor__tech-card">
      <div className="admission-editor__program-header">
        <strong>Тех. контакт {index + 1}</strong>
        <button type="button" className="ghost" onClick={() => onRemove(index)}>
          Удалить
        </button>
      </div>
      <div className="admission-editor__grid">
        <label>
          <span>Имя</span>
          <input
            value={contact.name}
            onChange={(event) => onChange(index, { ...contact, name: event.target.value })}
          />
        </label>
        <label>
          <span>Телефон</span>
          <input
            value={contact.phone}
            onChange={(event) => onChange(index, { ...contact, phone: event.target.value })}
          />
        </label>
      </div>
      <label>
        <span>Примечание</span>
        <textarea
          rows={2}
          value={contact.note ?? ""}
          onChange={(event) => onChange(index, { ...contact, note: event.target.value })}
        />
      </label>
    </article>
  );
}

function SectionShell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="feature-section">
      <div className="feature-section__header">
        <div>
          <p className="eyebrow">Admissions</p>
          <h2>{title}</h2>
          <p className="muted">{description}</p>
        </div>
      </div>
      <div className="panel admission-editor">{children}</div>
    </section>
  );
}

function GeneralSection({
  formState,
  setFormState,
}: {
  formState: AdmissionInfoPayload;
  setFormState: Dispatch<SetStateAction<AdmissionInfoPayload | null>>;
}) {
  return (
    <SectionShell
      title="Общие данные"
      description="Базовая информация о вузе и служебные поля admission_info.json."
    >
      <div className="admission-editor__grid">
        <label>
          <span>Учреждение</span>
          <input
            value={formState.institution}
            onChange={(event) => setFormState((current) => current ? { ...current, institution: event.target.value } : current)}
          />
        </label>
        <label>
          <span>Валюта</span>
          <input
            value={formState.currency}
            onChange={(event) => setFormState((current) => current ? { ...current, currency: event.target.value } : current)}
          />
        </label>
        <label>
          <span>Последнее обновление</span>
          <input value={formState.last_updated ?? ""} readOnly />
        </label>
      </div>
    </SectionShell>
  );
}

function ContactsSection({
  formState,
  updateContacts,
  updateTechnicalContact,
  removeTechnicalContact,
}: {
  formState: AdmissionInfoPayload;
  updateContacts: (field: string, value: unknown) => void;
  updateTechnicalContact: (index: number, nextValue: AdmissionTechnicalContact) => void;
  removeTechnicalContact: (index: number) => void;
}) {
  return (
    <SectionShell
      title="Контакты"
      description="Отдельная страница для контактов приемной комиссии и технических контактов."
    >
      <div className="admission-editor__grid">
        <label>
          <span>Отдел</span>
          <input value={formState.contacts.department ?? ""} onChange={(event) => updateContacts("department", event.target.value)} />
        </label>
        <label>
          <span>Сайт</span>
          <input value={String(formState.contacts.website ?? "")} onChange={(event) => updateContacts("website", event.target.value)} />
        </label>
      </div>

      <label>
        <span>Адрес</span>
        <textarea rows={3} value={formState.contacts.address ?? ""} onChange={(event) => updateContacts("address", event.target.value)} />
      </label>

      <label>
        <span>Часы работы</span>
        <textarea rows={2} value={formState.contacts.working_hours ?? ""} onChange={(event) => updateContacts("working_hours", event.target.value)} />
      </label>

      <div className="admission-editor__grid">
        <label>
          <span>Телефоны, по одному на строку</span>
          <textarea
            rows={4}
            value={arrayToLines(formState.contacts.phone)}
            onChange={(event) => updateContacts("phone", linesToArray(event.target.value))}
          />
        </label>
        <label>
          <span>Email, по одному на строку</span>
          <textarea
            rows={4}
            value={arrayToLines(formState.contacts.email)}
            onChange={(event) => updateContacts("email", linesToArray(event.target.value))}
          />
        </label>
      </div>

      <div className="admission-editor__section-header">
        <strong>Технические контакты</strong>
        <button
          type="button"
          className="ghost"
          onClick={() => updateContacts("technical_contacts", [...(formState.contacts.technical_contacts ?? []), createEmptyTechnicalContact()])}
        >
          Добавить контакт
        </button>
      </div>

      <div className="admission-editor__stack">
        {(formState.contacts.technical_contacts ?? []).map((contact, index) => (
          <TechnicalContactCard
            key={`${contact.name}-${index}`}
            contact={contact}
            index={index}
            onChange={updateTechnicalContact}
            onRemove={removeTechnicalContact}
          />
        ))}
      </div>
    </SectionShell>
  );
}

function ProgramsSection({
  programs,
  updateProgram,
  removeProgram,
  addProgram,
}: {
  programs: AdmissionProgram[];
  updateProgram: (index: number, nextValue: AdmissionProgram) => void;
  removeProgram: (index: number) => void;
  addProgram: () => void;
}) {
  return (
    <SectionShell
      title="Специальности"
      description="Каждая образовательная программа редактируется отдельно."
    >
      <div className="admission-editor__section-header">
        <div>
          <strong>Программы</strong>
          <p className="muted">Стоимость и проходные баллы редактируются прямо в карточке программы.</p>
        </div>
        <button type="button" className="ghost" onClick={addProgram}>
          Добавить программу
        </button>
      </div>

      <div className="admission-editor__stack">
        {programs.map((program, index) => (
          <ProgramCard
            key={`${program.id ?? program.name}-${index}`}
            program={program}
            index={index}
            onChange={updateProgram}
            onRemove={removeProgram}
          />
        ))}
      </div>
    </SectionShell>
  );
}

function JsonSection({
  title,
  description,
  value,
  onChange,
}: {
  title: string;
  description: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <SectionShell title={title} description={description}>
      <label>
        <span>JSON</span>
        <textarea rows={20} value={value} onChange={(event) => onChange(event.target.value)} />
      </label>
    </SectionShell>
  );
}

function AdmissionInfoEditor() {
  const queryClient = useQueryClient();
  const location = useLocation();
  const [formState, setFormState] = useState<AdmissionInfoPayload | null>(null);
  const [durationRulesText, setDurationRulesText] = useState("{}");
  const [documentsText, setDocumentsText] = useState("{}");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const admissionInfoQuery = useQuery({
    queryKey: ["admission-info"],
    queryFn: fetchAdmissionInfo,
  });

  useEffect(() => {
    if (!admissionInfoQuery.data?.data) return;
    const payload = clonePayload(admissionInfoQuery.data.data);
    setFormState(payload);
    setDurationRulesText(JSON.stringify(payload.duration_rules ?? {}, null, 2));
    setDocumentsText(JSON.stringify(payload.documents ?? {}, null, 2));
    setErrorMessage(null);
  }, [admissionInfoQuery.data]);

  const saveMutation = useMutation({
    mutationFn: updateAdmissionInfo,
    onSuccess: (response) => {
      queryClient.setQueryData(["admission-info"], response);
      setSuccessMessage("Изменения сохранены в admission_info.json.");
      setErrorMessage(null);
    },
    onError: (error) => {
      setSuccessMessage(null);
      setErrorMessage(error instanceof Error ? error.message : "Не удалось сохранить admission_info.json.");
    },
  });

  if (admissionInfoQuery.isLoading || !formState) {
    return <SectionShell title="Admissions" description="Загрузка admission-данных..."><p>Загрузка...</p></SectionShell>;
  }

  if (admissionInfoQuery.isError) {
    return <SectionShell title="Admissions" description="Не удалось загрузить данные."><p className="error">Ошибка загрузки.</p></SectionShell>;
  }

  const pathname = location.pathname.replace(/\/+$/, "");
  const lastSegment = pathname.split("/").pop() || "general";
  const section = ADMISSION_SECTIONS.some((item) => item.key === lastSegment)
    ? (lastSegment as AdmissionSectionKey)
    : "general";

  const sourcePath = admissionInfoQuery.data?.source_path ?? "";

  const updateContacts = (field: string, value: unknown) => {
    setFormState((current) => {
      if (!current) return current;
      return {
        ...current,
        contacts: {
          ...current.contacts,
          [field]: value,
        },
      };
    });
  };

  const updateProgram = (index: number, nextValue: AdmissionProgram) => {
    setFormState((current) => {
      if (!current) return current;
      const programs = [...current.programs];
      programs[index] = nextValue;
      return { ...current, programs };
    });
  };

  const removeProgram = (index: number) => {
    setFormState((current) => {
      if (!current) return current;
      return {
        ...current,
        programs: current.programs.filter((_, itemIndex) => itemIndex !== index),
      };
    });
  };

  const updateTechnicalContact = (index: number, nextValue: AdmissionTechnicalContact) => {
    const currentContacts = Array.isArray(formState.contacts.technical_contacts)
      ? formState.contacts.technical_contacts
      : [];
    const nextContacts = [...currentContacts];
    nextContacts[index] = nextValue;
    updateContacts("technical_contacts", nextContacts);
  };

  const removeTechnicalContact = (index: number) => {
    const currentContacts = Array.isArray(formState.contacts.technical_contacts)
      ? formState.contacts.technical_contacts
      : [];
    updateContacts(
      "technical_contacts",
      currentContacts.filter((_, itemIndex) => itemIndex !== index),
    );
  };

  const handleReset = () => {
    if (!admissionInfoQuery.data?.data) return;
    const payload = clonePayload(admissionInfoQuery.data.data);
    setFormState(payload);
    setDurationRulesText(JSON.stringify(payload.duration_rules ?? {}, null, 2));
    setDocumentsText(JSON.stringify(payload.documents ?? {}, null, 2));
    setErrorMessage(null);
    setSuccessMessage(null);
  };

  const handleSave = () => {
    try {
      const payload: AdmissionInfoPayload = {
        ...formState,
        contacts: {
          ...formState.contacts,
          phone: formState.contacts.phone ?? [],
          email: formState.contacts.email ?? [],
          technical_contacts: (formState.contacts.technical_contacts ?? []).map((contact) => ({
            ...contact,
            name: contact.name.trim(),
            phone: contact.phone.trim(),
            note: (contact.note ?? "").trim(),
          })),
        },
        duration_rules: parseJsonSection("Блок duration_rules", durationRulesText),
        documents: parseJsonSection("Блок documents", documentsText),
        programs: formState.programs.map((program) => ({
          ...program,
          name: program.name.trim(),
          id: (program.id ?? "").trim(),
          name_ru: (program.name_ru ?? "").trim(),
          name_kk: (program.name_kk ?? "").trim(),
          name_en: (program.name_en ?? "").trim(),
          aliases: (program.aliases ?? []).map((item) => item.trim()).filter(Boolean),
          duration: typeof program.duration === "string" ? program.duration.trim() : program.duration,
          tuition: {
            ...program.tuition,
            period: typeof program.tuition.period === "string" ? program.tuition.period.trim() : program.tuition.period,
          },
          passing_score: {
            ...program.passing_score,
            exam: typeof program.passing_score.exam === "string" ? program.passing_score.exam.trim() : program.passing_score.exam,
            notes: (program.passing_score.notes ?? []).map((item) => item.trim()).filter(Boolean),
          },
        })),
      };
      setSuccessMessage(null);
      setErrorMessage(null);
      saveMutation.mutate(payload);
    } catch (error) {
      setSuccessMessage(null);
      setErrorMessage(error instanceof Error ? error.message : "Не удалось подготовить данные к сохранению.");
    }
  };

  let content: ReactNode = null;
  if (section === "general") {
    content = <GeneralSection formState={formState} setFormState={setFormState} />;
  } else if (section === "contacts") {
    content = (
      <ContactsSection
        formState={formState}
        updateContacts={updateContacts}
        updateTechnicalContact={updateTechnicalContact}
        removeTechnicalContact={removeTechnicalContact}
      />
    );
  } else if (section === "programs") {
    content = (
      <ProgramsSection
        programs={formState.programs}
        updateProgram={updateProgram}
        removeProgram={removeProgram}
        addProgram={() => setFormState((current) => current ? { ...current, programs: [...current.programs, createEmptyProgram()] } : current)}
      />
    );
  } else if (section === "durations") {
    content = (
      <JsonSection
        title="Сроки обучения"
        description="Отдельная страница для блока duration_rules."
        value={durationRulesText}
        onChange={setDurationRulesText}
      />
    );
  } else if (section === "documents") {
    content = (
      <JsonSection
        title="Документы"
        description="Отдельная страница для блока documents."
        value={documentsText}
        onChange={setDocumentsText}
      />
    );
  } else if (section === "applications") {
    content = <AdmissionApplications />;
  }

  return (
    <div className="admissions-admin-page">
      <div className="feature-section admissions-admin-shell">
        <div className="feature-section__header">
          <div>
            <p className="eyebrow">Admissions</p>
            <h2>Управление admission_info.json</h2>
            <p className="muted">Каждый блок вынесен на отдельную страницу внутри раздела admissions.</p>
          </div>
          <span className="feature-section__status">{formState.programs.length} programs</span>
        </div>

        <div className="admin-toolbar">
          <div className="admin-toolbar__summary">
            <strong>Файл: {sourcePath}</strong>
            <span className="muted">Последнее обновление: {formState.last_updated || "не указано"}</span>
          </div>
          {section !== "applications" ? (
            <div className="admission-editor__actions">
              <button type="button" className="ghost" onClick={handleReset} disabled={saveMutation.isPending}>
                Сбросить
              </button>
              <button type="button" className="primary" onClick={handleSave} disabled={saveMutation.isPending}>
                {saveMutation.isPending ? "Сохранение..." : "Сохранить"}
              </button>
            </div>
          ) : null}
        </div>

        {errorMessage ? <p className="error">{errorMessage}</p> : null}
        {successMessage ? <p className="success-text">{successMessage}</p> : null}

        <div className="admissions-admin-layout">
          <aside className="admissions-admin-sidebar">
            {ADMISSION_SECTIONS.map((item) => (
              <NavLink
                key={item.key}
                to={`/admissions/${item.key}`}
                className={({ isActive }) => `admissions-admin-sidebar__link${isActive ? " active" : ""}`}
              >
                {item.label}
              </NavLink>
            ))}
          </aside>
          <div className="admissions-admin-content">
            {content}
          </div>
        </div>
      </div>
    </div>
  );
}

export function AdmissionsAdmin() {
  const location = useLocation();
  if (location.pathname === "/admissions" || location.pathname === "/admissions/") {
    return <Navigate to="/admissions/general" replace />;
  }
  return <AdmissionInfoEditor />;
}
