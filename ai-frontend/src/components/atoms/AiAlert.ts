import { escapeHtml } from "../../utils/dom";

export function createAiAlert(
  message: string,
  level: "info" | "success" | "warning" | "danger" = "info",
): HTMLElement {
  const el = document.createElement("div");
  el.className = `alert alert-${level} ai-alert`;
  el.setAttribute("role", "alert");
  el.innerHTML = escapeHtml(message);
  return el;
}
