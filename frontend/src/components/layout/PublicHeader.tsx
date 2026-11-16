import { NavLink } from "react-router-dom";
import { Icon } from "../ui/Icon";
import { Logo } from "../ui/Logo";
import { ThemeToggle } from "../ui/ThemeToggle";

export function PublicHeader() {
  return (
    <header className="public-header">
      <div className="public-header__inner">
        <Logo to="/" subtitle="Turan-Astana University" />
        <nav className="public-header__nav" aria-label="Разделы">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "is-active" : undefined)}>
            Главная
          </NavLink>
          <NavLink to="/chat" className={({ isActive }) => (isActive ? "is-active" : undefined)}>
            Чат приёмной
          </NavLink>
        </nav>
        <div className="public-header__actions">
          <ThemeToggle />
          <NavLink to="/telegram-login" className="ghost btn--sm">
            <Icon name="user" size={16} />
            <span>Войти</span>
          </NavLink>
        </div>
      </div>
    </header>
  );
}
