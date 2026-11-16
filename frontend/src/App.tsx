import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { apiClient, AUTH_STORAGE_EVENT, hasStoredSession } from "./api/client";
import { ChatWorkspace } from "./components/chat/ChatWorkspace";
import { AppShell } from "./components/layout/AppShell";
import { PublicHeader } from "./components/layout/PublicHeader";
import { PublicLanding } from "./components/PublicLanding";
import { TelegramLogin } from "./components/TelegramLogin";

// Admin screens are code-split: students and applicants never download them.
const named = <T extends Record<string, unknown>>(loader: () => Promise<T>, key: keyof T) =>
  lazy(() => loader().then((module) => ({ default: module[key] as React.ComponentType })));

const Profile = named(() => import("./components/Profile"), "Profile");
const RagManager = named(() => import("./components/RagManager"), "RagManager");
const RagDocumentDetail = named(() => import("./components/RagDocumentDetail"), "RagDocumentDetail");
const RagJobs = named(() => import("./components/RagJobs"), "RagJobs");
const AgentsDashboard = named(() => import("./components/AgentsDashboard"), "AgentsDashboard");
const PlatonusStatus = named(() => import("./components/PlatonusStatus"), "PlatonusStatus");
const AdmissionsAdmin = named(() => import("./components/AdmissionsAdmin"), "AdmissionsAdmin");
const ChatAnalytics = named(() => import("./components/ChatAnalytics"), "ChatAnalytics");
const ChatUsers = named(() => import("./components/ChatUsers"), "ChatUsers");
const MiniApp = named(() => import("./components/MiniApp"), "MiniApp");

const ADMIN_ROLES = new Set(["admin", "administrator", "superuser", "staff", "dean", "deanery"]);
const isAdminRole = (role?: string | null) => Boolean(role && ADMIN_ROLES.has(role.trim().toLowerCase()));

function PageLoader() {
  return (
    <div className="page-loader" role="status" aria-live="polite">
      <span className="spinner" />
      <span className="muted">Загрузка…</span>
    </div>
  );
}

function RequireAuth({ isAuthenticated, children }: { isAuthenticated: boolean; children: ReactNode }) {
  if (!isAuthenticated) return <Navigate to="/telegram-login" replace />;
  return <>{children}</>;
}

function AdminGate({ isAdmin, isResolved, children }: { isAdmin: boolean; isResolved: boolean; children: ReactNode }) {
  if (!isResolved) return <PageLoader />;
  if (!isAdmin) return <Navigate to="/profile" replace />;
  return <>{children}</>;
}

function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="public-layout">
      <PublicHeader />
      <main className="public-main">{children}</main>
      <footer className="public-footer">
        <span>© {new Date().getFullYear()} Turan-Astana University</span>
        <span className="muted">Ответы ИИ носят справочный характер</span>
      </footer>
    </div>
  );
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => hasStoredSession());
  const [isAdmin, setIsAdmin] = useState(false);
  const [isAdminResolved, setIsAdminResolved] = useState(() => !hasStoredSession());

  useEffect(() => {
    const handleAuthChanged = () => setIsAuthenticated(hasStoredSession());
    window.addEventListener(AUTH_STORAGE_EVENT, handleAuthChanged);
    window.addEventListener("storage", handleAuthChanged);
    return () => {
      window.removeEventListener(AUTH_STORAGE_EVENT, handleAuthChanged);
      window.removeEventListener("storage", handleAuthChanged);
    };
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      setIsAdmin(false);
      setIsAdminResolved(true);
      return;
    }
    let active = true;
    setIsAdminResolved(false);
    apiClient
      .get<{ status: string; user: { role?: string | null } }>("/auth/me")
      .then((response) => active && setIsAdmin(isAdminRole(response.user.role ?? null)))
      .catch(() => active && setIsAdmin(false))
      .finally(() => active && setIsAdminResolved(true));
    return () => {
      active = false;
    };
  }, [isAuthenticated]);

  const shell = (node: ReactNode, adminOnly = false) => (
    <RequireAuth isAuthenticated={isAuthenticated}>
      <AppShell isAdmin={isAdmin}>
        <Suspense fallback={<PageLoader />}>
          {adminOnly ? (
            <AdminGate isAdmin={isAdmin} isResolved={isAdminResolved}>
              {node}
            </AdminGate>
          ) : (
            node
          )}
        </Suspense>
      </AppShell>
    </RequireAuth>
  );

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={isAuthenticated ? <Navigate to="/chat" replace /> : <PublicLayout><PublicLanding /></PublicLayout>}
        />
        <Route
          path="/chat"
          element={<ChatWorkspace key={isAuthenticated ? "private" : "public"} mode={isAuthenticated ? "private" : "publicAdmission"} isAdmin={isAdmin} />}
        />
        <Route path="/telegram-login" element={<TelegramLogin />} />
        <Route path="/mini-app" element={<Suspense fallback={<PageLoader />}><div className="mini-app-page"><MiniApp /></div></Suspense>} />

        <Route path="/profile" element={shell(<Profile />)} />
        <Route path="/rag" element={shell(<RagManager />, true)} />
        <Route path="/rag/:documentId" element={shell(<RagDocumentDetail />, true)} />
        <Route path="/rag-jobs" element={shell(<RagJobs />, true)} />
        <Route path="/agents" element={shell(<AgentsDashboard />, true)} />
        <Route path="/platonus" element={shell(<PlatonusStatus />, true)} />
        <Route path="/admissions/*" element={shell(<AdmissionsAdmin />, true)} />
        <Route path="/chat-analytics/*" element={shell(<ChatAnalytics />, true)} />
        <Route path="/chat-users" element={shell(<ChatUsers />, true)} />
        <Route path="/llm" element={<Navigate to="/agents" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
