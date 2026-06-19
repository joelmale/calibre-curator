import type { IIngestionRunStatus } from "../../types/status";
import { formatRelativeTime, formatDateTime } from "../../utils/format";
import { createAiStatusTable } from "./AiStatusTable";

const RUN_STATUS_CLASS: Record<string, string> = {
  completed: "label-success",
  partial:   "label-warning",
  failed:    "label-danger",
  running:   "label-info",
};

export function createAiRunStats(run: IIngestionRunStatus): HTMLElement {
  const isRunning = run.status === "running";

  const statusBadge = document.createElement("span");
  statusBadge.className = `label ${RUN_STATUS_CLASS[run.status] ?? "label-default"}`;
  statusBadge.textContent = isRunning ? "Running…" : run.status;

  const startedEl = document.createElement("span");
  startedEl.title = formatDateTime(run.startedAt);
  startedEl.textContent = formatRelativeTime(run.startedAt);

  const wrapper = document.createElement("div");

  if (isRunning) {
    // Show a clear "in-progress" message rather than misleading 0s
    const notice = document.createElement("div");
    notice.className = "alert-info";
    notice.style.cssText = "margin:8px;font-size:12px;padding:8px;border:1px solid;border-radius:4px;";
    notice.innerHTML = `<strong>Run in progress</strong> — started ${formatRelativeTime(run.startedAt)}. Refresh in a moment to see results.`;
    wrapper.appendChild(notice);
    return wrapper;
  }

  const rows: Array<readonly [string, HTMLElement | string]> = [
    ["Last scan",       startedEl],
    ["Status",          statusBadge],
    ["Books scanned",   run.scannedBooks != null ? run.scannedBooks.toLocaleString() : "—"],
    ["Changed/queued",  run.changedBooks  != null ? run.changedBooks.toLocaleString()  : "—"],
    ["Chunks embedded", run.embeddedChunks != null ? run.embeddedChunks.toLocaleString() : "—"],
  ];

  if (run.errorCount > 0) {
    const errBadge = document.createElement("span");
    errBadge.className = "label label-danger";
    errBadge.textContent = run.errorCount.toLocaleString();
    rows.push(["Errors", errBadge]);
  }

  if (run.finishedAt) {
    const finEl = document.createElement("span");
    finEl.title = formatDateTime(run.finishedAt);
    finEl.textContent = formatRelativeTime(run.finishedAt);
    rows.push(["Finished", finEl]);
  }

  wrapper.appendChild(createAiStatusTable(rows));

  // If the run completed but embedded 0 chunks and status is not "running",
  // show an explanatory hint — this is what the user saw as confusing.
  if (run.embeddedChunks === 0 && run.changedBooks === 0 && !isRunning) {
    const hint = document.createElement("div");
    hint.style.cssText = "margin:8px;padding:6px 10px;font-size:11px;border-radius:4px;background:var(--ai-color-info-bg);color:var(--ai-color-info);border:1px solid var(--ai-color-info-border);";
    hint.textContent = "No new or changed books were detected — pending books will be processed on upcoming scans.";
    wrapper.appendChild(hint);
  }

  return wrapper;
}
