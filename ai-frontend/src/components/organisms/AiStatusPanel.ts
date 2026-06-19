import type { IAiStatusResponse } from "../../types/status";
import { createAiProgressBar } from "../atoms/AiProgressBar";
import { createAiStatusTable } from "../molecules/AiStatusTable";
import { createAiRunStats } from "../molecules/AiRunStats";
import {
  createAiDonutChart,
  createAiStatusBarChart,
  breakdownToSlices,
} from "../molecules/AiDonutChart";

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

  // Progress cell: count + bar
  const progressCell = document.createElement("div");
  progressCell.innerHTML = `${s.library.indexedBookCount.toLocaleString()} / ${s.library.bookCount.toLocaleString()}`;
  progressCell.appendChild(createAiProgressBar(indexedPct));

  const libraryTable = createAiStatusTable([
    ["Calibre db",   dbBadge],
    ["Total books",  s.library.bookCount.toLocaleString()],
    ["Indexed",      progressCell],
    ["Pending",      s.library.pendingBookCount.toLocaleString()],
  ]);

  // ── Donut + bar charts ─────────────────────────────────────────────────────
  const bd = s.library.statusBreakdown ?? {};
  const slices = breakdownToSlices(bd);

  const chartsSection = document.createElement("div");
  chartsSection.style.cssText = "padding:8px 0 4px;display:flex;flex-direction:column;gap:12px;";

  // Donut (status breakdown)
  const donutHeading = document.createElement("div");
  donutHeading.style.cssText = "font-size:11px;font-weight:600;color:var(--ai-color-text-muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;";
  donutHeading.textContent = "Status Breakdown";
  chartsSection.appendChild(donutHeading);
  chartsSection.appendChild(createAiDonutChart(slices));

  // Bar chart
  const barHeading = document.createElement("div");
  barHeading.style.cssText = "font-size:11px;font-weight:600;color:var(--ai-color-text-muted);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;margin-top:4px;";
  barHeading.textContent = "By Status (count)";
  chartsSection.appendChild(barHeading);
  chartsSection.appendChild(createAiStatusBarChart(bd));

  const libContainer = document.createElement("div");
  libContainer.appendChild(libraryTable);
  libContainer.appendChild(chartsSection);

  // Pending-backlog hint (user-visible counterpart to the Part-1 fix)
  if (s.library.pendingBookCount > 0) {
    const lastRun = s.lastIngestionRun;
    const wasStuck = !lastRun || (lastRun.status !== "running" && lastRun.embeddedChunks === 0 && lastRun.changedBooks === 0);
    if (wasStuck) {
      const hint = document.createElement("div");
      hint.className = "alert-info";
      hint.style.cssText = "margin:4px 0 0;font-size:12px;padding:8px;border:1px solid;border-radius:4px;";
      hint.textContent =
        `${s.library.pendingBookCount.toLocaleString()} book${s.library.pendingBookCount === 1 ? "" : "s"} pending — they'll be processed on upcoming scans.`;
      libContainer.appendChild(hint);
    }
  }

  const libraryPanel = _panel("Library Index", libContainer);

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
    ["Model",    modelCode],
    ["Status",   statusBadge],
  ];

  // Chat / generation fallback chain
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

  // Prominent embedding warning when Ollama is unreachable / model not pulled
  if (s.embedding.warning) {
    const warn = document.createElement("div");
    warn.className = `alert ${s.embedding.ok ? "alert-warning" : "alert-danger"}`;
    warn.style.margin = "8px";
    warn.style.fontSize = "12px";
    warn.innerHTML = `<strong>${s.embedding.ok ? "Warning" : "Embedding unavailable"}:</strong> ${s.embedding.warning}`;
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
