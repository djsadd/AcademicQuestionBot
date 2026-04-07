import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient, authStorage } from "../api/client";

type ProfileResponse = {
  status: string;
  user: {
    telegram_id: number;
    username?: string | null;
    first_name?: string | null;
    last_name?: string | null;
    person_id?: string | null;
    platonus_auth?: boolean;
    role?: string | null;
  };
};

const PROFILE_URL = "https://academiq.tau-edu.kz/#/profile";

export function Profile() {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    apiClient
      .get<ProfileResponse>("/auth/me")
      .then((response) => {
        if (active) {
          setProfile(response);
        }
      })
      .catch((err) => {
        if (active) {
          const message = err instanceof Error ? err.message : "Failed to load profile.";
          setError(message);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleLogout() {
    const refreshToken = authStorage.getRefreshToken();
    setIsLoggingOut(true);
    setError(null);
    try {
      if (refreshToken) {
        await apiClient.post("/auth/logout", JSON.stringify({ refresh_token: refreshToken }));
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Logout failed.";
      setError(message);
    } finally {
      authStorage.clearTokens();
      setIsLoggingOut(false);
      navigate("/telegram-login", { replace: true });
    }
  }

  return (
    <section className="panel">
      <div className="profile-panel__header">
        <div>
          <h2>Профиль</h2>
          <p className="muted">Управление доступом и переход в личный кабинет.</p>
        </div>
        <div className="profile-panel__actions">
          <a className="ghost" href={PROFILE_URL} target="_blank" rel="noreferrer">
            Открыть профиль
          </a>
          <button className="ghost profile-panel__logout" onClick={handleLogout} disabled={isLoggingOut}>
            {isLoggingOut ? "Выходим..." : "Выйти"}
          </button>
        </div>
      </div>
      {error ? <p className="error">{error}</p> : null}
      {profile ? (
        <div className="status-card">
          <div className="status-card__header">
            <strong>Аккаунт</strong>
            <span className="status-pill status-success">OK</span>
          </div>
          <p className="muted">ID: {profile.user.telegram_id}</p>
          <p className="muted">Логин: {profile.user.username ?? "—"}</p>
          <p className="muted">Person ID: {profile.user.person_id ?? "—"}</p>
          <p className="muted">Роль: {profile.user.role ?? "—"}</p>
          <p className="muted">Страница профиля: {PROFILE_URL}</p>
        </div>
      ) : (
        <p className="muted">Загрузка...</p>
      )}
    </section>
  );
}
