const SAFE_URL_RE = /^(https?:\/\/|\/)/;

export function sanitizeUrl(url: string | null | undefined): string {
  if (!url) return "#";
  return SAFE_URL_RE.test(url) ? url : "#";
}

export function escapeHtml(value: string): string {
  const el = document.createElement("span");
  el.textContent = value;
  return el.innerHTML;
}
