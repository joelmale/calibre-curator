import { escapeHtml } from "../../utils/dom";

export function createAiEmptyState(message: string): HTMLElement {
  const el = document.createElement("div");
  el.className = "ai-empty-state text-center text-muted";
  el.innerHTML = `<p>${escapeHtml(message)}</p>`;
  return el;
}
