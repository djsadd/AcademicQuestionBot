export function formatBytes(bytes: number): string {
  if (!bytes) return "0 Б";
  const sizes = ["Б", "КБ", "МБ", "ГБ"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), sizes.length - 1);
  const value = bytes / Math.pow(1024, i);
  return `${value >= 10 || i === 0 ? Math.round(value) : value.toFixed(1)} ${sizes[i]}`;
}

export function formatDate(dateString?: string | null): string {
  if (!dateString) return "—";
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("ru-RU", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

const RELATIVE = new Intl.RelativeTimeFormat("ru", { numeric: "auto" });

export function formatRelative(dateString?: string | null): string {
  if (!dateString) return "—";
  const time = new Date(dateString).getTime();
  if (Number.isNaN(time)) return "—";
  const diff = (time - Date.now()) / 1000;
  const units: [Intl.RelativeTimeFormatUnit, number][] = [["year", 31536000], ["month", 2592000], ["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [unit, seconds] of units) {
    if (Math.abs(diff) >= seconds) return RELATIVE.format(Math.round(diff / seconds), unit);
  }
  return "только что";
}

export function formatNumber(value?: number | null): string {
  return value === null || value === undefined ? "—" : value.toLocaleString("ru-RU");
}

export function pluralize(count: number, forms: [string, string, string]): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return forms[1];
  return forms[2];
}
