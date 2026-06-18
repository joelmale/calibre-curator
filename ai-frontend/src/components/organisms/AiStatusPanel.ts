import type { IAiStatusResponse } from "../../types/status";
import { createAiProgressBar } from "../atoms/AiProgressBar";
import { createAiStatusTable } from "../molecules/AiStatusTable";
import { createAiRunStats } from "../molecules/AiRunStats";

export function createAiStatusPanel(s: IAiStatusResponse): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.className = "row ai-status-panel";

  // ── Library panel ──────────────────────────────────────────────────────────
  const indexedPct =
    s.library.bookCount > 0
      ? (s.library.indexedBookCount / s.library.bookCount) * 100
      : 0;

  const dbBadge = document.createElement("span");
  dbBadge.className = `label ${s.library.metadataDbReadable ? "label-success" : "label-danger"}`;
  dbBadge.textContent = s.library.metadataDbReadable ? "Readable" : "Not found";

  const progressCell = document.createElement("div");
  progressCell.innerHTML = `${s.library.indexedBookCount.toLocaleString()} / ${s.library.bookCount.toLocaleString()}`;
  progressCell.appendChild(createAiProgressBar(indexedPct));

  // Build breakdown string from statusBreakdown map
  const bd = s.library.statusBreakdown ?? {};
  const breakdownEl = document.createElement("span");
  const STATUS_ORDER = ["indexed", "chunked", "extracting", "failed", "pending"];
  const parts = STATUS_ORDER
    .filter(k => bd[k])
    .map(k => `${bd[k]?.toLocaleString()} ${k}`);
  // include any unexpected statuses too
  Object.keys(bd).filter(k => !STATUS_ORDER.includes(k)).forEach(k => {
    parts.push(`${bd[k]?.toLocaleString()} ${k}`);
  });
  breakdownEl.textContent = parts.length ? parts.join(" · ") : "—";
  breakdownEl.style.fontSize = "12px";
  breakdownEl.style.color = "#888";

  const libraryTable = createAiStatusTable([
    ["Calibre metadata.db", dbBadge],
    ["Total books", s.library.bookCount.toLocaleString()],
    ["Indexed", progressCell],
    ["Pending", s.library.pendingBookCount.toLocaleString()],
    ["Breakdown", breakdownEl],
  ]);

  const libraryPanel = _panel("Library Index", libraryTable);

  // ── Embedding + ingestion panel ────────────────────────────────────────────
  const providerCode = document.createElement("code");
  providerCode.textContent = s.embedding.provider;
  const modelCode = document.createElement("code");
  modelCode.textContent = s.embedding.model;

  const statusBadge = document.createElement("span");
  statusBadge.className = `label ${s.embedding.ok ? "label-success" : "label-danger"}`;
  statusBadge.textContent = s.embedding.ok ? "Ready" : "Not available";

  const embeddingRows: Array<readonly [string, HTMLElement | string]> = [
    ["Provider", providerCode],
    ["Model", modelCode],
    ["Status", statusBadge],
  ];

  // Chat / generation fallback chain (Enrichment, Mood, Sequences)
  if (s.chat && s.chat.chain.length > 0) {
    const chainEl = document.createElement("span");
    chainEl.style.fontSize = "12px";
    chainEl.textContent = s.chat.chain.join("  →  ");
    embeddingRows.push(["Chat fallback", chainEl]);
  }

  const embeddingTable = createAiStatusTable(embeddingRows);
  const runEl: HTMLElement = s.lastIngestionRun
    ? createAiRunStats(s.lastIngestionRun)
    : (() => {
        const p = document.createElement("p");
        p.className = "text-muted";
        p.style.padding = "8px";
        p.textContent = "No ingestion runs yet.";
        return p;
      })();

  const embFrag = document.createDocumentFragment();
  embFrag.appendChild(embeddingTable);
  if (s.embedding.warning) {
    const warn = document.createElement("div");
    warn.className = "alert alert-warning";
    warn.style.margin = "8px";
    warn.textContent = s.embedding.warning;
    embFrag.appendChild(warn);
  }
  embFrag.appendChild(runEl);
  const embContainer = document.createElement("div");
  embContainer.appendChild(embFrag);
  const embeddingPanel = _panel("Embedding & Ingestion", embContainer);

  const libCol = document.createElement("div");
  libCol.className = "col-sm-6";
  libCol.appendChild(libraryPanel);

  const embCol = document.createElement("div");
  embCol.className = "col-sm-6";
  embCol.appendChild(embeddingPanel);

  wrapper.appendChild(libCol);
  wrapper.appendChild(embCol);
  return wrapper;
}

function _panel(title: string, content: HTMLElement): HTMLElement {
  const panel = document.createElement("div");
  panel.className = "panel panel-default";

  const heading = document.createElement("div");
  heading.className = "panel-heading";
  heading.innerHTML = `<h3 class="panel-title">${title}</h3>`;

  panel.appendChild(heading);
  panel.appendChild(content);
  return panel;
}
