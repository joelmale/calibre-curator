import type { IIngestionRunStatus } from "../../types/status";
import { formatDateTime } from "../../utils/format";
import { escapeHtml } from "../../utils/dom";
import { createAiStatusTable } from "./AiStatusTable";

export function createAiRunStats(run: IIngestionRunStatus): HTMLElement {
  const statusCode = document.createElement("code");
  statusCode.textContent = run.status;

  return createAiStatusTable([
    ["Last scan",      formatDateTime(run.startedAt)],
    ["Status",         statusCode],
    ["Books scanned",  run.scannedBooks.toLocaleString()],
    ["Chunks embedded", run.embeddedChunks.toLocaleString()],
    ["Errors",         escapeHtml(String(run.errorCount))],
  ]);
}
