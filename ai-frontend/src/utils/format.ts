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

export function joinAuthors(authors: readonly string[]): string {
  return authors.join(", ");
}
