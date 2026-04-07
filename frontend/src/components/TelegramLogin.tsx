import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient, authStorage } from "../api/client";

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
  const [profile, setProfile] = useState<PasswordLoginResponse | null>(null);
  const navigate = useNavigate();

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
      setProfile(response);
      navigate("/profile", { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="telegram-login login-screen">
      <div className="mini-app__card telegram-login__card login-form-card">
        <div className="login-form-card__hero">
          <p className="eyebrow">Platonus Access</p>
          <h2>Вход в аккаунт</h2>
          <p className="muted">
            Войдите в систему, чтобы открыть персональный доступ к сервисам AcademicQuestionBot.
          </p>
          <div className="login-form-card__chips">
            <span>Личный кабинет</span>
            <span>Защищенная сессия</span>
            <span>Быстрый вход</span>
          </div>
        </div>
        <form className="mini-app__form" onSubmit={handleSubmit}>
          <label className="mini-app__field">
            <span>Логин</span>
            <input
              name="login"
              autoComplete="username"
              placeholder="Введите логин"
              value={login}
              onChange={(event) => setLogin(event.target.value)}
              disabled={busy}
            />
          </label>
          <label className="mini-app__field">
            <span>Пароль</span>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              placeholder="Введите пароль"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={busy}
            />
          </label>
          <button className="primary" type="submit" disabled={busy}>
            {busy ? "Проверяем..." : "Войти"}
          </button>
        </form>
        {error ? <p className="mini-app__status error">{error}</p> : null}
        {profile ? (
          <div className="status-card">
            <div className="status-card__header">
              <strong>Профиль</strong>
              <span className="status-pill status-success">OK</span>
            </div>
            <p className="muted">Логин: {profile.user.username ?? "—"}</p>
            <p className="muted">Внутренний ID: {profile.user.telegram_id}</p>
            <p className="muted">Доступ подтвержден.</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
