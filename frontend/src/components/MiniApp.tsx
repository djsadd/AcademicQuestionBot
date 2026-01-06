import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";

const TRANSLATIONS = {
  kk: {
    login: "Логин",
    password: "Құпиясөз",
    loginPlaceholder: "student.login",
    passwordPlaceholder: "********",
    agree: "Ережелер мен құпиялылық саясатын қабылдаймын.",
    submit: "Кіру",
    submitting: "Тексерілуде...",
    statusMissingTg: "Telegram қолданушысы табылмады. Форманы бот арқылы ашыңыз.",
    statusDone: "Рұқсат беру аяқталды. Ботқа қайта оралыңыз.",
    statusFailed: "Авторизация сәтсіз аяқталды.",
  },
  ru: {
    login: "Логин",
    password: "Пароль",
    loginPlaceholder: "student.login",
    passwordPlaceholder: "********",
    agree: "Я принимаю правила и политику конфиденциальности.",
    submit: "Войти",
    submitting: "Проверяем...",
    statusMissingTg: "Telegram пользователь не найден. Откройте форму из бота.",
    statusDone: "Авторизация завершена. Вернитесь в бота.",
    statusFailed: "Ошибка авторизации.",
  },
  en: {
    login: "Login",
    password: "Password",
    loginPlaceholder: "student.login",
    passwordPlaceholder: "********",
    agree: "I agree to the rules and privacy policy.",
    submit: "Sign in",
    submitting: "Checking...",
    statusMissingTg: "Telegram user not found. Open this form from the bot.",
    statusDone: "Authorization completed. Return to the bot.",
    statusFailed: "Authorization failed.",
  },
} as const;

type Language = keyof typeof TRANSLATIONS;

export function MiniApp() {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [telegramId, setTelegramId] = useState<number | null>(null);
  const [initData, setInitData] = useState<string>("");
  const [language, setLanguage] = useState<Language>("ru");

  useEffect(() => {
    const readInitDataFromUrl = () => {
      const searchParams = new URLSearchParams(window.location.search);
      const direct = searchParams.get("tgWebAppData");
      if (direct) {
        return direct;
      }
      const hash = window.location.hash || "";
      const hashQuery = hash.includes("?") ? hash.split("?")[1] ?? "" : "";
      if (!hashQuery) {
        return "";
      }
      const hashParams = new URLSearchParams(hashQuery);
      return hashParams.get("tgWebAppData") ?? "";
    };

    const webApp = (window as any)?.Telegram?.WebApp;
    if (webApp?.ready) {
      webApp.ready();
    }
    const readId = () => {
      const id = webApp?.initDataUnsafe?.user?.id;
      if (typeof id === "number") {
        setTelegramId(id);
        if (typeof webApp?.initData === "string") {
          setInitData(webApp.initData);
        }
        return true;
      }
      const receiverId = webApp?.initDataUnsafe?.receiver?.id;
      if (typeof receiverId === "number") {
        setTelegramId(receiverId);
        if (typeof webApp?.initData === "string") {
          setInitData(webApp.initData);
        }
        return true;
      }
      if (typeof webApp?.initData === "string" && webApp.initData.length > 0) {
        setInitData(webApp.initData);
      }
      return false;
    };

    if (readId()) {
      return;
    }

    const urlInitData = readInitDataFromUrl();
    if (urlInitData) {
      setInitData(urlInitData);
    }

    let tries = 0;
    const interval = window.setInterval(() => {
      tries += 1;
      if (readId() || tries >= 10) {
        window.clearInterval(interval);
      }
    }, 200);

    return () => {
      window.clearInterval(interval);
    };
  }, []);

  const t = useMemo(() => TRANSLATIONS[language], [language]);

  const canSubmit =
    login.trim().length > 0 && password.trim().length > 0 && agreed && !busy;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    if (!telegramId && !initData) {
      setStatus(t.statusMissingTg);
      return;
    }
    setBusy(true);
    setStatus(null);
    try {
      await apiClient.post("/telegram/auth", JSON.stringify({
        telegram_id: telegramId,
        init_data: initData,
        login,
        password,
        agreed,
      }));
      setStatus(t.statusDone);
    } catch (error) {
      const message = error instanceof Error ? error.message : t.statusFailed;
      setStatus(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mini-app">
      <div className="mini-app__card">
        <div className="mini-app__lang">
          <button
            type="button"
            className={language === "kk" ? "active" : undefined}
            onClick={() => setLanguage("kk")}
          >
            Қазақша
          </button>
          <button
            type="button"
            className={language === "ru" ? "active" : undefined}
            onClick={() => setLanguage("ru")}
          >
            Русский
          </button>
          <button
            type="button"
            className={language === "en" ? "active" : undefined}
            onClick={() => setLanguage("en")}
          >
            English
          </button>
        </div>

        <form className="mini-app__form" onSubmit={handleSubmit}>
          <label className="mini-app__field">
            <span>{t.login}</span>
            <input
              type="text"
              name="login"
              placeholder={t.loginPlaceholder}
              value={login}
              onChange={(event) => setLogin(event.target.value)}
              autoComplete="username"
            />
          </label>

          <label className="mini-app__field">
            <span>{t.password}</span>
            <input
              type="password"
              name="password"
              placeholder={t.passwordPlaceholder}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>

          <label className="mini-app__agreement">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(event) => setAgreed(event.target.checked)}
            />
            <span>{t.agree}</span>
          </label>

          <button className="primary" type="submit" disabled={!canSubmit}>
            {busy ? t.submitting : t.submit}
          </button>

          {status ? <p className="mini-app__status">{status}</p> : null}
        </form>
      </div>
    </section>
  );
}
