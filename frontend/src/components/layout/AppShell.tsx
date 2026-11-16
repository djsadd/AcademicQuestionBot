import { useEffect, useState, type ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { apiClient, authStorage } from "../../api/client";
import { Icon, type IconName } from "../ui/Icon";
import { Logo } from "../ui/Logo";
import { ThemeToggle } from "../ui/ThemeToggle";

type NavItem = { path: string; label: string; icon: IconName; adminOnly?: boolean };
type NavGroup = { title: string; items: NavItem[] };

export const NAV_GROUPS: NavGroup[] = [
  {
    title: "Ассистент",
    items: [
      { path: "/chat", label: "Чат", icon: "chat" },
      { path: "/profile", label: "Профиль", icon: "user" },
    ],
  },
  {
    title: "База знаний",
    items: [
      { path: "/rag", label: "Документы", icon: "database", adminOnly: true },
      { path: "/rag-jobs", label: "Журнал индексации", icon: "layers", adminOnly: true },
      { path: "/admissions", label: "Приёмная комиссия", icon: "cap", adminOnly: true },
    ],
  },
  {
    title: "Мониторинг",
    items: [
      { path: "/agents", label: "Агенты", icon: "cpu", adminOnly: true },
      { path: "/chat-analytics", label: "Диалоги", icon: "chart", adminOnly: true },
      { path: "/chat-users", label: "Пользователи", icon: "users", adminOnly: true },
      { path: "/platonus", label: "Platonus", icon: "link", adminOnly: true },
    ],
  },
];

const PAGE_TITLES: Record<string, string> = {
  ...Object.fromEntries(NAV_GROUPS.flatMap((group) => group.items.map((item) => [item.path, item.label]))),
  "/rag": "База знаний",
};

function usePageTitle(pathname: string) {
  const match = Object.keys(PAGE_TITLES)
    .sort((a, b) => b.length - a.length)
    .find((path) => pathname === path || pathname.startsWith(`${path}/`));
  return match ? PAGE_TITLES[match] : "Academiq";
}

export function AppShell({ isAdmin, children }: { isAdmin: boolean; children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const title = usePageTitle(location.pathname);

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    document.title = `${title} · Academiq`;
  }, [title]);

  const handleLogout = async () => {
    setLoggingOut(true);
    const refreshToken = authStorage.getRefreshToken();
    try {
      if (refreshToken) {
        await apiClient.post("/auth/logout", JSON.stringify({ refresh_token: refreshToken }));
      }
    } catch {
      // Tokens are cleared locally anyway.
    } finally {
      authStorage.clearTokens();
      setLoggingOut(false);
      navigate("/telegram-login", { replace: true });
    }
  };

  return (
    <div className={`app-shell${drawerOpen ? " app-shell--drawer-open" : ""}`}>
      <aside className="app-sidebar" aria-label="Основная навигация">
        <div className="app-sidebar__head">
          <Logo to="/chat" subtitle="TAU Assistant" />
          <button type="button" className="icon-button app-sidebar__close" onClick={() => setDrawerOpen(false)} aria-label="Закрыть меню">
            <Icon name="x" />
          </button>
        </div>
        <nav className="app-nav">
          {NAV_GROUPS.map((group) => {
            const items = group.items.filter((item) => !item.adminOnly || isAdmin);
            if (!items.length) return null;
            return (
              <div className="app-nav__group" key={group.title}>
                <span className="app-nav__title">{group.title}</span>
                {items.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive }) => `app-nav__link${isActive ? " is-active" : ""}`}
                  >
                    <Icon name={item.icon} />
                    <span>{item.label}</span>
                  </NavLink>
                ))}
              </div>
            );
          })}
        </nav>
        <div className="app-sidebar__foot">
          <button type="button" className="app-nav__link app-nav__link--button" onClick={handleLogout} disabled={loggingOut}>
            <Icon name="logout" />
            <span>{loggingOut ? "Выходим…" : "Выйти"}</span>
          </button>
        </div>
      </aside>
      <div className="app-backdrop" onClick={() => setDrawerOpen(false)} aria-hidden="true" />

      <div className="app-main">
        <header className="app-topbar">
          <button type="button" className="icon-button app-topbar__menu" onClick={() => setDrawerOpen(true)} aria-label="Открыть меню">
            <Icon name="menu" />
          </button>
          <h1 className="app-topbar__title">{title}</h1>
          <div className="app-topbar__actions">
            <ThemeToggle />
            <NavLink to="/chat" className="primary btn--sm">
              <Icon name="sparkles" size={16} />
              <span>Спросить ИИ</span>
            </NavLink>
          </div>
        </header>
        <main className="app-content">{children}</main>
      </div>
    </div>
  );
}
