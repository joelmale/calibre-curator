import type { IIngestionFailure } from "../../types/api";
import { formatRelativeTime, formatDateTime } from "../../utils/format";

/**
 * AiRecentFailures — collapsible list of recently-failed ingestion books.
 *
 * Shows a summary count as the toggle label; expands to reveal the
 * calibre book ID, title, error message, and time of failure.
 */
export function createAiRecentFailures(failures: readonly IIngestionFailure[]): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.className = "ai-recent-failures";
  wrapper.style.cssText = "margin-top:8px;";

  if (failures.length === 0) {
    return wrapper; // nothing to show
  }

  // Collapsible details element
  const details = document.createElement("details");
  details.style.cssText =
    "border:1px solid var(--ai-color-danger-border);" +
    "border-radius:var(--ai-radius);" +
    "background:var(--ai-color-danger-bg);";

  const summary = document.createElement("summary");
  summary.style.cssText =
    "cursor:pointer;padding:6px 10px;font-size:12px;font-weight:600;" +
    "color:var(--ai-color-danger);list-style:none;user-select:none;";
  summary.textContent = `${failures.length} recent failure${failures.length === 1 ? "" : "s"} — click to expand`;

  const list = document.createElement("div");
  list.style.cssText = "padding:4px 8px 8px;max-height:260px;overflow-y:auto;";

  for (const f of failures) {
    const item = document.createElement("div");
    item.style.cssText =
      "padding:5px 0;border-bottom:1px solid var(--ai-color-danger-border);font-size:11px;";

    const titleLine = document.createElement("div");
    titleLine.style.cssText = "color:var(--ai-color-text);font-weight:600;margin-bottom:1px;";
    titleLine.textContent = `#${f.calibreBookId} — ${f.title ?? "(untitled)"}`;

    const errorLine = document.createElement("div");
    errorLine.style.cssText = "color:var(--ai-color-danger);word-break:break-word;";
    errorLine.textContent = f.error ?? "Unknown error";

    const timeLine = document.createElement("div");
    timeLine.style.cssText = "color:var(--ai-color-text-muted);margin-top:1px;";
    timeLine.title = formatDateTime(f.failedAt);
    timeLine.textContent = formatRelativeTime(f.failedAt);

    item.appendChild(titleLine);
    item.appendChild(errorLine);
    item.appendChild(timeLine);
    list.appendChild(item);
  }

  details.appendChild(summary);
  details.appendChild(list);
  wrapper.appendChild(details);
  return wrapper;
}
