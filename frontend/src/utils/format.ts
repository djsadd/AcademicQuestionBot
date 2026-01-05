export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), sizes.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
}

export function formatDate(dateString: string): string {
  if (!dateString) return "—";
  const date = new Date(dateString);
  return date.toLocaleString();
}
