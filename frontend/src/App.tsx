import { HashRouter, NavLink, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { RagDocumentDetail } from "./components/RagDocumentDetail";
import { RagJobs } from "./components/RagJobs";
import { RagManager } from "./components/RagManager";
import { FakeChat } from "./components/FakeChat";
import { MiniApp } from "./components/MiniApp";

const NAV_ITEMS = [
  { id: "rag", label: "RAG", path: "/rag" },
  { id: "rag-jobs", label: "JOBS", path: "/rag-jobs" },
  { id: "llm", label: "LLM", path: "/llm" },
  { id: "chat", label: "CHAT", path: "/chat" },
  { id: "agents", label: "AGENTS", path: "/agents" },
  { id: "miniapp", label: "MINI APP", path: "/mini-app" },
] as const;

type PageId = (typeof NAV_ITEMS)[number]["id"];

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

function SiteHeader() {
  return (
    <header className="site-header">
      <div className="logo">AcademicQuestionBot</div>
      <nav>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.id}
            to={item.path}
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            {item.label}
          </NavLink>
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

function FeaturePage({ pageId }: { pageId: PageId }) {
  const featureSection = FEATURE_SECTIONS.find((section) => section.id === pageId);
  return featureSection ? <FeatureSection key={featureSection.id} {...featureSection} /> : null;
}

function RagPage() {
  return (
    <>
      <Hero />
      <RagManager sectionId="rag" />
    </>
  );
}

function MiniAppPage() {
  return (
    <div className="mini-app-page">
      <main className="mini-app-page__main">
        <MiniApp />
      </main>
    </div>
  );
}

function MainLayout() {
  return (
    <>
      <SiteHeader />
      <main className="page-main">
        <Outlet />
      </main>
    </>
  );
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Navigate to="/rag" replace />} />
          <Route path="/rag" element={<RagPage />} />
          <Route path="/rag/:documentId" element={<RagDocumentDetail />} />
          <Route path="/rag-jobs" element={<RagJobs />} />
          <Route path="/llm" element={<FeaturePage pageId="llm" />} />
          <Route path="/chat" element={<FakeChat />} />
          <Route path="/agents" element={<FeaturePage pageId="agents" />} />
        </Route>
        <Route path="/mini-app" element={<MiniAppPage />} />
        <Route path="*" element={<Navigate to="/rag" replace />} />
      </Routes>
    </HashRouter>
  );
}
