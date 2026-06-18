export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const abs = Math.abs(diff);
    if (abs < 60_000) return "just now";
    if (abs < 3_600_000) return `${Math.round(abs / 60_000)}m ago`;
    if (abs < 86_400_000) return `${Math.round(abs / 3_600_000)}h ago`;
    return `${Math.round(abs / 86_400_000)}d ago`;
  } catch {
    return iso;
  }
}

export function joinAuthors(authors: readonly string[]): string {
  return authors.join(", ");
}
