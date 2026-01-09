import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient, authStorage } from "../api/client";

type TelegramAuthPayload = {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
};

type TelegramLoginResponse = {
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
  };
};

declare global {
  interface Window {
    handleTelegramAuth?: (user: TelegramAuthPayload) => void;
  }
}

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME ?? "";

export function TelegramLogin() {
  const widgetRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<TelegramLoginResponse | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!BOT_USERNAME) {
      setError("VITE_TELEGRAM_BOT_USERNAME is not configured.");
      return;
    }

    window.handleTelegramAuth = async (user: TelegramAuthPayload) => {
      setBusy(true);
      setError(null);
      try {
        const response = await apiClient.post<TelegramLoginResponse>(
          "/auth/telegram",
          JSON.stringify(user),
        );
        authStorage.setTokens(response.access_token, response.refresh_token);
        setProfile(response);
        navigate("/profile", { replace: true });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Telegram login failed.";
        setError(message);
      } finally {
        setBusy(false);
      }
    };

    const container = widgetRef.current;
    if (!container) {
      return () => undefined;
    }

    container.innerHTML = "";
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.setAttribute("data-telegram-login", BOT_USERNAME);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-userpic", "false");
    script.setAttribute("data-radius", "12");
    script.setAttribute("data-onauth", "handleTelegramAuth(user)");
    container.appendChild(script);

    return () => {
      if (widgetRef.current) {
        widgetRef.current.innerHTML = "";
      }
      delete window.handleTelegramAuth;
    };
  }, []);

  return (
    <section className="telegram-login">
      <div className="mini-app__card telegram-login__card">
        <p className="eyebrow">Telegram</p>
        <h2>Вход через Telegram</h2>
        <p className="muted">
          Авторизация через виджет Telegram выдаст доступ к веб-интерфейсу. Мы проверяем
          подпись через токен бота.
        </p>
        <div ref={widgetRef} className="telegram-login__widget" />
        {busy ? <p className="mini-app__status">Проверяем...</p> : null}
        {error ? <p className="mini-app__status error">{error}</p> : null}
        {profile ? (
          <div className="status-card">
            <div className="status-card__header">
              <strong>Профиль</strong>
              <span className="status-pill status-success">OK</span>
            </div>
            <p className="muted">
              Telegram ID: {profile.user.telegram_id}
              {profile.user.username ? `, @${profile.user.username}` : ""}
            </p>
            {profile.user.platonus_auth ? (
              <p className="muted">Platonus доступ подтвержден.</p>
            ) : (
              <p className="muted">Platonus еще не привязан.</p>
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}
