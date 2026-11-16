import { Link } from "react-router-dom";

export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <span className="logo-mark" style={{ width: size, height: size }} aria-hidden="true">
      <svg viewBox="0 0 32 32" width={size} height={size}>
        <rect width="32" height="32" rx="9" fill="var(--brand-solid)" />
        <path d="M8 13.2 16 9l8 4.2-8 4.2-8-4.2Z" fill="#fff" />
        <path d="M11.5 15.4v4.1c0 1.3 2 2.5 4.5 2.5s4.5-1.2 4.5-2.5v-4.1L16 17.8l-4.5-2.4Z" fill="#fff" opacity=".78" />
        <circle cx="24" cy="18.5" r="1.2" fill="#fff" />
        <path d="M24 13.4v4.6" stroke="#fff" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    </span>
  );
}

export function Logo({ to = "/", subtitle }: { to?: string; subtitle?: string }) {
  return (
    <Link to={to} className="logo" aria-label="Academiq — на главную">
      <LogoMark />
      <span className="logo__text">
        <span className="logo__title">Academiq</span>
        {subtitle ? <span className="logo__subtitle">{subtitle}</span> : null}
      </span>
    </Link>
  );
}
