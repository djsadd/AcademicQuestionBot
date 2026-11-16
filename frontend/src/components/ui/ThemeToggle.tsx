import { useTheme } from "../../theme";
import { Icon } from "./Icon";

export function ThemeToggle({ className = "" }: { className?: string }) {
  const { resolved, toggle } = useTheme();
  const label = resolved === "dark" ? "Включить светлую тему" : "Включить тёмную тему";
  return (
    <button type="button" className={`icon-button ${className}`} onClick={toggle} aria-label={label} title={label}>
      <Icon name={resolved === "dark" ? "sun" : "moon"} />
    </button>
  );
}
