import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiClient, authStorage } from "../api/client";
import { Icon } from "./ui/Icon";
import { Logo } from "./ui/Logo";
import { ThemeToggle } from "./ui/ThemeToggle";

type PasswordLoginResponse = {
  status: string;
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  refresh_expires_in: number;
  user: {
    telegram_id: number;
    username?: string | null;
    first_name?: string | null;
    last_name?: string | null;
    platonus_auth?: boolean;
    role?: string | null;
    person_id?: string | null;
    iin?: string | null;
    fullname?: string | null;
    statusName?: string | null;
    email?: string | null;
  };
};

export function TelegramLogin() {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    document.title = "Вход · Academiq";
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!login.trim() || !password.trim()) {
      setError("Введите логин и пароль.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const response = await apiClient.post<PasswordLoginResponse>(
        "/auth/login",
        JSON.stringify({
          login: login.trim(),
          password,
        }),
      );
      authStorage.setTokens(response.access_token, response.refresh_token);
      navigate("/chat", { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <aside className="auth-page__brand">
        <Logo to="/" subtitle="Turan-Astana University" />
        <div className="auth-page__pitch">
          <h2>Ваш академический ассистент</h2>
          <ul>
            <li><Icon name="calendar" size={18} /> Персональный академический календарь из Platonus</li>
            <li><Icon name="book" size={18} /> Ответы по регламентам и документам университета</li>
            <li><Icon name="sparkles" size={18} /> История диалогов на всех устройствах</li>
          </ul>
        </div>
        <span className="auth-page__copy">© {new Date().getFullYear()} Turan-Astana University</span>
      </aside>

      <main className="auth-page__main">
        <div className="auth-page__top">
          <Link to="/" className="auth-page__back">
            <Icon name="arrowRight" size={16} style={{ transform: "rotate(180deg)" }} /> На главную
          </Link>
          <ThemeToggle />
        </div>
        <div className="auth-card">
          <div className="auth-card__head">
            <h1>Вход в аккаунт</h1>
            <p className="muted">Используйте логин и пароль от Platonus.</p>
          </div>
          <form className="auth-form" onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span className="field__label">Логин</span>
              <input
                name="login"
                autoComplete="username"
                placeholder="Логин Platonus"
                value={login}
                onChange={(event) => setLogin(event.target.value)}
                disabled={busy}
                autoFocus
              />
            </label>
            <label className="field">
              <span className="field__label">Пароль</span>
              <span className="field__control">
                <input
                  type={showPassword ? "text" : "password"}
                  name="password"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={busy}
                />
                <button
                  type="button"
                  className="field__suffix"
                  onClick={() => setShowPassword((value) => !value)}
                  aria-label={showPassword ? "Скрыть пароль" : "Показать пароль"}
                >
                  {showPassword ? "Скрыть" : "Показать"}
                </button>
              </span>
            </label>
            {error ? (
              <div className="auth-form__error" role="alert">
                <Icon name="alert" size={16} /> {error}
              </div>
            ) : null}
            <button className="primary btn--lg auth-form__submit" type="submit" disabled={busy}>
              {busy ? <span className="spinner spinner--on-brand" /> : null}
              {busy ? "Проверяем…" : "Войти"}
            </button>
          </form>
          <div className="auth-card__foot">
            <span className="muted">Абитуриент?</span>
            <Link to="/chat">Спросить приёмную комиссию без входа</Link>
          </div>
        </div>
      </main>
    </div>
  );
}
