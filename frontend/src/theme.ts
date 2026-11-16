import { useCallback, useEffect, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "aqb_theme";
const THEME_EVENT = "aqb-theme-changed";

function readPreference(): ThemePreference {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === "light" || value === "dark" || value === "system") return value;
  } catch {
    // Storage may be unavailable (private mode); fall back to the OS setting.
  }
  return "system";
}

export function applyTheme(preference: ThemePreference) {
  const root = document.documentElement;
  if (preference === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", preference);
  }
}

function resolvedTheme(preference: ThemePreference): "light" | "dark" {
  if (preference !== "system") return preference;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Call once before React renders to avoid a flash of the wrong theme. */
export function initTheme() {
  applyTheme(readPreference());
}

export function useTheme() {
  const [preference, setPreference] = useState<ThemePreference>(readPreference);
  const [resolved, setResolved] = useState<"light" | "dark">(() => resolvedTheme(readPreference()));

  useEffect(() => {
    const sync = () => {
      const next = readPreference();
      setPreference(next);
      setResolved(resolvedTheme(next));
    };
    const media = window.matchMedia?.("(prefers-color-scheme: dark)");
    window.addEventListener(THEME_EVENT, sync);
    media?.addEventListener?.("change", sync);
    return () => {
      window.removeEventListener(THEME_EVENT, sync);
      media?.removeEventListener?.("change", sync);
    };
  }, []);

  const setTheme = useCallback((next: ThemePreference) => {
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Ignore storage errors; the theme still applies for this page view.
    }
    applyTheme(next);
    window.dispatchEvent(new Event(THEME_EVENT));
  }, []);

  const toggle = useCallback(() => {
    setTheme(resolvedTheme(readPreference()) === "dark" ? "light" : "dark");
  }, [setTheme]);

  return { preference, resolved, setTheme, toggle };
}
