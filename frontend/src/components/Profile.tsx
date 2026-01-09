import { useEffect, useState } from "react";
import { apiClient } from "../api/client";

type ProfileResponse = {
  status: string;
  user: {
    telegram_id: number;
    person_id?: string | null;
    platonus_auth?: boolean;
  };
};

export function Profile() {
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <section className="panel">
      <h2>Профиль</h2>
      {error ? <p className="error">{error}</p> : null}
      {profile ? (
        <div className="status-card">
          <div className="status-card__header">
            <strong>Telegram</strong>
            <span className="status-pill status-success">OK</span>
          </div>
          <p className="muted">Telegram ID: {profile.user.telegram_id}</p>
          <p className="muted">
            Person ID: {profile.user.person_id ?? "—"}
          </p>
        </div>
      ) : (
        <p className="muted">Загрузка...</p>
      )}
    </section>
  );
}
