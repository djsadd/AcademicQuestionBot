import { useEffect, useMemo, useState } from "react";
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

type AdmissionTab = "editor" | "applications";

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
          <p className="muted">Редактирование карточки программы</p>
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
          <span>Грант сокращённый курс</span>
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

function AdmissionInfoEditor() {
  const queryClient = useQueryClient();
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

  const programCount = useMemo(() => formState?.programs.length ?? 0, [formState?.programs.length]);

  if (admissionInfoQuery.isLoading || !formState) {
    return (
      <section className="feature-section">
        <div className="feature-section__header">
          <div>
            <p className="eyebrow">Admissions</p>
            <h2>Редактор admission_info.json</h2>
          </div>
        </div>
        <p>Загрузка admission-данных...</p>
      </section>
    );
  }

  if (admissionInfoQuery.isError) {
    return (
      <section className="feature-section">
        <div className="feature-section__header">
          <div>
            <p className="eyebrow">Admissions</p>
            <h2>Редактор admission_info.json</h2>
          </div>
        </div>
        <p className="error">Не удалось загрузить admission-данные.</p>
      </section>
    );
  }

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

  return (
    <section className="feature-section">
      <div className="feature-section__header">
        <div>
          <p className="eyebrow">Admissions</p>
          <h2>Редактор admission_info.json</h2>
          <p className="muted">
            Основные поля вынесены в форму, сложные блоки `documents` и `duration_rules` можно править отдельно.
          </p>
        </div>
        <span className="feature-section__status">{programCount} programs</span>
      </div>

      <div className="panel admission-editor">
        <div className="admin-toolbar">
          <div className="admin-toolbar__summary">
            <strong>Файл: {sourcePath}</strong>
            <span className="muted">Последнее обновление: {formState.last_updated || "не указано"}</span>
          </div>
          <div className="admission-editor__actions">
            <button type="button" className="ghost" onClick={handleReset} disabled={saveMutation.isPending}>
              Сбросить
            </button>
            <button type="button" className="primary" onClick={handleSave} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Сохранение..." : "Сохранить"}
            </button>
          </div>
        </div>

        {errorMessage ? <p className="error">{errorMessage}</p> : null}
        {successMessage ? <p className="success-text">{successMessage}</p> : null}

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
        </div>

        <section className="admission-editor__section">
          <div className="feature-section__header">
            <div>
              <h3>Контакты</h3>
              <p className="muted">Быстрое редактирование контактного блока.</p>
            </div>
          </div>

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
        </section>

        <section className="admission-editor__section">
          <div className="admission-editor__section-header">
            <div>
              <h3>Программы</h3>
              <p className="muted">Основные поля программ редактируются без открытия JSON.</p>
            </div>
            <button
              type="button"
              className="ghost"
              onClick={() => setFormState((current) => current ? { ...current, programs: [...current.programs, createEmptyProgram()] } : current)}
            >
              Добавить программу
            </button>
          </div>

          <div className="admission-editor__stack">
            {formState.programs.map((program, index) => (
              <ProgramCard
                key={`${program.id ?? program.name}-${index}`}
                program={program}
                index={index}
                onChange={updateProgram}
                onRemove={removeProgram}
              />
            ))}
          </div>
        </section>

        <section className="admission-editor__section">
          <div className="feature-section__header">
            <div>
              <h3>Сложные блоки</h3>
              <p className="muted">Для `documents` и `duration_rules` пока оставлен JSON-режим, чтобы не ломать вложенные структуры.</p>
            </div>
          </div>

          <label>
            <span>duration_rules</span>
            <textarea rows={12} value={durationRulesText} onChange={(event) => setDurationRulesText(event.target.value)} />
          </label>

          <label>
            <span>documents</span>
            <textarea rows={16} value={documentsText} onChange={(event) => setDocumentsText(event.target.value)} />
          </label>
        </section>
      </div>
    </section>
  );
}

export function AdmissionsAdmin() {
  const [activeTab, setActiveTab] = useState<AdmissionTab>("editor");

  return (
    <div className="admissions-admin-page">
      <div className="admissions-admin-tabs">
        <button
          type="button"
          className={activeTab === "editor" ? "primary" : "ghost"}
          onClick={() => setActiveTab("editor")}
        >
          Редактор данных
        </button>
        <button
          type="button"
          className={activeTab === "applications" ? "primary" : "ghost"}
          onClick={() => setActiveTab("applications")}
        >
          Заявки
        </button>
      </div>

      {activeTab === "editor" ? <AdmissionInfoEditor /> : <AdmissionApplications />}
    </div>
  );
}
