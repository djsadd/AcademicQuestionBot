import { useState } from "react";
import { RagManager } from "./components/RagManager";
import { FakeChat } from "./components/FakeChat";

const NAV_ITEMS = [
  { id: "rag", label: "RAG" },
  { id: "llm", label: "LLM" },
  { id: "chat", label: "CHAT" },
  { id: "agents", label: "AGENTS" },
] as const;

type PageId = (typeof NAV_ITEMS)[number]["id"];

const DEFAULT_PAGE: PageId = NAV_ITEMS[0].id;

const FEATURE_SECTIONS = [
  {
    id: "llm",
    eyebrow: "LLM",
    title: "Финальный ответ языковой модели",
    description:
      "Бэкенд агрегирует выводы агентов и отдает их в LLM-клиент, чтобы получить связный итоговый ответ.",
    status: "Готово на бэкенде",
    bullets: [
      "Поддержка OpenAI API и локальных моделей (см. backend/langchain/llm.py)",
      "Автоматическая проверка контента и повтор отправки при ошибках",
    ],
  },
  {
    id: "chat",
    eyebrow: "Chat",
    title: "Тестовый чат для инженеров знаний",
    description:
      "Слой веб-чата позволит обкатывать сценарии до выката в прод, а также собирать обратную связь от пользователей.",
    status: "UI в разработке",
    bullets: [
      "Стриминговый REST/WebSocket API для сообщений",
      "Логи экспериментов и сохранение истории диалогов на сервере",
    ],
  },
  {
    id: "agents",
    eyebrow: "Agents",
    title: "Оркестрация и наблюдаемость агентов",
    description:
      "Workflow объединяет планировщика, агрегатор фактов и финальный ответ. События трекаются, чтобы отслеживать качество.",
    status: "Бэкенд online",
    bullets: [
      "Каждый агент работает с единой шиной контекста",
      "Отправка метрик и логов в OpenTelemetry / Prometheus",
    ],
  },
] as const;

interface SiteHeaderProps {
  activePage: PageId;
  onNavigate: (pageId: PageId) => void;
}

function SiteHeader({ activePage, onNavigate }: SiteHeaderProps) {
  return (
    <header className="site-header">
      <div className="logo">AcademicQuestionBot</div>
      <nav>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onNavigate(item.id)}
            className={item.id === activePage ? "active" : undefined}
            aria-current={item.id === activePage ? "page" : undefined}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <a className="ghost docs-link" href="README.MD" target="_blank" rel="noreferrer">
        README
      </a>
    </header>
  );
}

function Hero() {
  return (
    <section className="hero">
      <div>
        <p className="eyebrow">Academic Question Bot</p>
        <h1>Единый интерфейс для академических ответов</h1>
        <p className="muted">
          Подключите RAG-документы, следите за статусом агентов и протестируйте чат прямо в браузере.
        </p>
        <div className="hero-actions">
          <button className="primary">Открыть чат (скоро)</button>
          <button
            className="ghost"
            onClick={() => document.getElementById("rag")?.scrollIntoView({ behavior: "smooth" })}
          >
            Управлять RAG
          </button>
        </div>
      </div>
      <div className="hero-card">
        <h3>Статус сервисов</h3>
        <ul>
          <li>
            <span className="dot success" /> API · Online
          </li>
          <li>
            <span className="dot success" /> Orchestrator · Ready
          </li>
          <li>
            <span className="dot success" /> RAG · Qdrant connected
          </li>
        </ul>
      </div>
    </section>
  );
}

function FeatureSection({
  eyebrow,
  title,
  description,
  bullets,
  status,
  id,
}: (typeof FEATURE_SECTIONS)[number]) {
  return (
    <section className="feature-section" id={id}>
      <p className="eyebrow">{eyebrow}</p>
      <div className="feature-section__header">
        <div>
          <h2>{title}</h2>
          <p className="muted">{description}</p>
        </div>
        <span className="feature-section__status">{status}</span>
      </div>
      <ul>
        {bullets.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function PageContent({ pageId }: { pageId: PageId }) {
  if (pageId === "rag") {
    return (
      <>
        <Hero />
        <RagManager sectionId="rag" />
      </>
    );
  }

  if (pageId === "chat") {
    return <FakeChat />;
  }

  const featureSection = FEATURE_SECTIONS.find((section) => section.id === pageId);

  if (!featureSection) {
    return null;
  }

  return <FeatureSection key={featureSection.id} {...featureSection} />;
}

export default function App() {
  const [activePage, setActivePage] = useState<PageId>(DEFAULT_PAGE);

  return (
    <>
      <SiteHeader activePage={activePage} onNavigate={setActivePage} />
      <main>
        <PageContent pageId={activePage} />
      </main>
    </>
  );
}
