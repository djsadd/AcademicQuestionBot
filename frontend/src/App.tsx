import { useEffect, useMemo, useState } from "react";
import { BrowserRouter, NavLink, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { RagDocumentDetail } from "./components/RagDocumentDetail";
import { RagJobs } from "./components/RagJobs";
import { RagManager } from "./components/RagManager";
import { FakeChat } from "./components/FakeChat";
import { MiniApp } from "./components/MiniApp";
import { PlatonusStatus } from "./components/PlatonusStatus";
import { TelegramLogin } from "./components/TelegramLogin";
import { Profile } from "./components/Profile";
import { AdmissionsAdmin } from "./components/AdmissionsAdmin";
import { ChatAnalytics } from "./components/ChatAnalytics";
import { PublicLanding } from "./components/PublicLanding";
import { apiClient, AUTH_STORAGE_EVENT, authStorage, hasStoredSession } from "./api/client";

const NAV_ITEMS = [
  { id: "profile", label: "PROFILE", path: "/profile" },
  { id: "rag", label: "RAG", path: "/rag" },
  { id: "rag-jobs", label: "JOBS", path: "/rag-jobs" },
  { id: "llm", label: "LLM", path: "/llm" },
  { id: "chat", label: "CHAT", path: "/chat" },
  { id: "agents", label: "AGENTS", path: "/agents" },
  { id: "platonus", label: "PLATONUS", path: "/platonus" },
  { id: "admissions", label: "ADMISSIONS", path: "/admissions" },
  { id: "chat-analytics", label: "CHAT LOGS", path: "/chat-analytics" },
] as const;

type PageId = (typeof NAV_ITEMS)[number]["id"];
type AdminOnlyId = "rag" | "rag-jobs" | "llm" | "agents" | "platonus" | "admissions" | "chat-analytics";

const ADMIN_ONLY_IDS: Set<AdminOnlyId> = new Set([
  "rag",
  "rag-jobs",
  "llm",
  "agents",
  "platonus",
  "admissions",
  "chat-analytics",
]);

const ADMIN_ROLES = new Set([
  "admin",
  "administrator",
  "superuser",
  "staff",
  "dean",
  "deanery",
]);

const isAdminRole = (role?: string | null) => {
  if (!role) return false;
  return ADMIN_ROLES.has(role.trim().toLowerCase());
};

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

function SiteHeader({ isAdmin, isAuthenticated }: { isAdmin: boolean; isAuthenticated: boolean }) {
  const navItems = useMemo(
    () =>
      isAuthenticated
        ? NAV_ITEMS.filter((item) => !ADMIN_ONLY_IDS.has(item.id as AdminOnlyId) || isAdmin)
        : [
          { id: "home", label: "HOME", path: "/" },
          { id: "chat", label: "CHAT", path: "/chat" },
        ],
    [isAdmin, isAuthenticated],
  );
  return (
    <header className="site-header">
      <NavLink to={isAuthenticated ? "/chat" : "/"} className="logo">
        AcademicQuestionBot
      </NavLink>
      <nav>
        {navItems.map((item) => (
          <NavLink
            key={item.id}
            to={item.path}
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      {isAuthenticated ? (
        <a className="ghost docs-link" href="README.MD" target="_blank" rel="noreferrer">
          README
        </a>
      ) : (
        <NavLink className="ghost docs-link" to="/telegram-login">
          LOGIN
        </NavLink>
      )}
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

function TelegramLoginPage() {
  return (
    <div className="mini-app-page">
      <main className="mini-app-page__main">
        <TelegramLogin />
      </main>
    </div>
  );
}

function MainLayout({
  isAdmin,
  isAuthenticated,
}: {
  isAdmin: boolean;
  isAuthenticated: boolean;
}) {
  const location = useLocation();
  const isChatPage = location.pathname === "/chat";
  return (
    <>
      {isChatPage ? null : <SiteHeader isAdmin={isAdmin} isAuthenticated={isAuthenticated} />}
      <main className={`page-main${isChatPage ? " page-main--no-scroll page-main--chat" : ""}`}>
        <Outlet />
      </main>
    </>
  );
}

function RequireAuth({ children }: { children: JSX.Element }) {
  if (!hasStoredSession()) {
    return <Navigate to="/telegram-login" replace />;
  }
  return children;
}

function RequireAdmin({ isAdmin, children }: { isAdmin: boolean; children: JSX.Element }) {
  if (!isAdmin) {
    return <Navigate to="/profile" replace />;
  }
  return children;
}

function AdminGate({
  isAdmin,
  isResolved,
  children,
}: {
  isAdmin: boolean;
  isResolved: boolean;
  children: JSX.Element;
}) {
  if (!isResolved) {
    return (
      <section className="panel">
        <p className="muted">Загрузка доступа...</p>
      </section>
    );
  }
  return <RequireAdmin isAdmin={isAdmin}>{children}</RequireAdmin>;
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => hasStoredSession());
  const [isAdmin, setIsAdmin] = useState(false);
  const [isAdminResolved, setIsAdminResolved] = useState(() => !hasStoredSession());

  useEffect(() => {
    const handleAuthChanged = () => {
      setIsAuthenticated(hasStoredSession());
    };

    window.addEventListener(AUTH_STORAGE_EVENT, handleAuthChanged);
    window.addEventListener("storage", handleAuthChanged);

    return () => {
      window.removeEventListener(AUTH_STORAGE_EVENT, handleAuthChanged);
      window.removeEventListener("storage", handleAuthChanged);
    };
  }, []);

  useEffect(() => {
    if (!hasStoredSession()) {
      setIsAdmin(false);
      setIsAdminResolved(true);
      return;
    }
    let active = true;
    setIsAdminResolved(false);
    apiClient
      .get<{ status: string; user: { role?: string | null } }>("/auth/me")
      .then((response) => {
        if (!active) return;
        setIsAdmin(isAdminRole(response.user.role ?? null));
        setIsAdminResolved(true);
      })
      .catch(() => {
        if (active) {
          setIsAdmin(false);
          setIsAdminResolved(true);
        }
      });
    return () => {
      active = false;
    };
  }, [isAuthenticated]);

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<MainLayout isAdmin={isAdmin} isAuthenticated={isAuthenticated} />}>
          <Route
            path="/"
            element={isAuthenticated ? <Navigate to="/profile" replace /> : <PublicLanding />}
          />
          <Route
            path="/chat"
            element={isAuthenticated ? <FakeChat /> : <FakeChat mode="publicAdmission" />}
          />
        </Route>
        <Route element={<RequireAuth><MainLayout isAdmin={isAdmin} isAuthenticated={isAuthenticated} /></RequireAuth>}>
          <Route path="/profile" element={<Profile />} />
          <Route
            path="/rag"
            element={<AdminGate isAdmin={isAdmin} isResolved={isAdminResolved}><RagPage /></AdminGate>}
          />
          <Route
            path="/rag/:documentId"
            element={<AdminGate isAdmin={isAdmin} isResolved={isAdminResolved}><RagDocumentDetail /></AdminGate>}
          />
          <Route
            path="/rag-jobs"
            element={<AdminGate isAdmin={isAdmin} isResolved={isAdminResolved}><RagJobs /></AdminGate>}
          />
          <Route
            path="/llm"
            element={<AdminGate isAdmin={isAdmin} isResolved={isAdminResolved}><FeaturePage pageId="llm" /></AdminGate>}
          />
          <Route
            path="/agents"
            element={<AdminGate isAdmin={isAdmin} isResolved={isAdminResolved}><FeaturePage pageId="agents" /></AdminGate>}
          />
          <Route
            path="/platonus"
            element={<AdminGate isAdmin={isAdmin} isResolved={isAdminResolved}><PlatonusStatus /></AdminGate>}
          />
          <Route
            path="/admissions/*"
            element={<AdminGate isAdmin={isAdmin} isResolved={isAdminResolved}><AdmissionsAdmin /></AdminGate>}
          />
          <Route
            path="/chat-analytics"
            element={<AdminGate isAdmin={isAdmin} isResolved={isAdminResolved}><ChatAnalytics /></AdminGate>}
          />
        </Route>
        <Route path="/mini-app" element={<MiniAppPage />} />
        <Route path="/telegram-login" element={<TelegramLoginPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
