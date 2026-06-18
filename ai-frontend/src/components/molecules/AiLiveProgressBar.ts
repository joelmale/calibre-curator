/**
 * AiLiveProgressBar — live indexed/total progress bar with throughput + ETA.
 *
 * - Prominent bar showing pct complete (indexed / total)
 * - Throughput (books/min during extracting, chunks/min during embedding)
 *   computed client-side from successive poll deltas
 * - ETA = remaining ÷ rate; shows "—" until a rate is known
 * - Handles both phases: extracting (per-book) and embedding (per-chunk)
 * - Token colors only
 */

import type { IIngestionProgress } from "../../types/status";

export interface LiveProgressBarEl extends HTMLElement {
  update(progress: IIngestionProgress): void;
}

interface RateSample {
  ts: number;   // Date.now()
  value: number; // current_index or chunks_embedded_so_far
}

let _styleInjected = false;
function injectStyles(): void {
  if (_styleInjected) return;
  _styleInjected = true;
  const style = document.createElement("style");
  style.textContent = `
    .ai-live-pb-wrap {
      padding: 8px 0 4px;
    }
    .ai-live-pb-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 4px;
      font-size: 12px;
    }
    .ai-live-pb-label {
      font-weight: 600;
      color: var(--ai-color-text);
    }
    .ai-live-pb-pct {
      color: var(--ai-color-text-muted);
    }
    .ai-live-pb-track {
      height: 12px;
      background: var(--ai-color-chart-track, var(--ai-color-surface-alt));
      border-radius: 6px;
      overflow: hidden;
      border: 1px solid var(--ai-color-border);
    }
    .ai-live-pb-fill {
      height: 100%;
      background: var(--ai-color-primary);
      border-radius: 6px;
      transition: width 0.4s ease;
    }
    .ai-live-pb-fill.embedding {
      background: var(--ai-color-info);
    }
    .ai-live-pb-meta {
      display: flex;
      gap: 16px;
      margin-top: 4px;
      font-size: 11px;
      color: var(--ai-color-text-muted);
    }
  `;
  document.head.appendChild(style);
}

export function createAiLiveProgressBar(progress: IIngestionProgress): LiveProgressBarEl {
  injectStyles();

  // Rate tracking: keep last two samples for delta computation
  const samples: RateSample[] = [];

  const wrapper = document.createElement("div") as unknown as LiveProgressBarEl;
  wrapper.className = "ai-live-pb-wrap";

  const header = document.createElement("div");
  header.className = "ai-live-pb-header";

  const labelEl = document.createElement("span");
  labelEl.className = "ai-live-pb-label";

  const pctEl = document.createElement("span");
  pctEl.className = "ai-live-pb-pct";

  header.appendChild(labelEl);
  header.appendChild(pctEl);

  const track = document.createElement("div");
  track.className = "ai-live-pb-track";

  const fill = document.createElement("div");
  fill.className = "ai-live-pb-fill";
  track.appendChild(fill);

  const meta = document.createElement("div");
  meta.className = "ai-live-pb-meta";

  const throughputEl = document.createElement("span");
  const etaEl = document.createElement("span");
  meta.appendChild(throughputEl);
  meta.appendChild(etaEl);

  wrapper.appendChild(header);
  wrapper.appendChild(track);
  wrapper.appendChild(meta);

  function computeRate(currentValue: number): number | null {
    const now = Date.now();
    // Push new sample; keep only last 2
    samples.push({ ts: now, value: currentValue });
    if (samples.length > 2) samples.shift();
    if (samples.length < 2) return null;
    const dt = (samples[1]!.ts - samples[0]!.ts) / 60_000; // minutes
    const dv = samples[1]!.value - samples[0]!.value;
    if (dt <= 0 || dv <= 0) return null;
    return dv / dt; // units per minute
  }

  function render(p: IIngestionProgress): void {
    if (p.phase === "idle") {
      wrapper.style.display = "none";
      return;
    }
    wrapper.style.display = "";

    const isEmbedding = p.phase === "embedding";

    if (isEmbedding) {
      fill.className = "ai-live-pb-fill embedding";
      const done = p.chunks_embedded_so_far;
      const total = p.chunks_total;
      const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
      labelEl.textContent = `Embedding chunks: ${done.toLocaleString()} / ${total.toLocaleString()}`;
      pctEl.textContent = `${pct}%`;
      fill.style.width = `${pct}%`;

      const rate = computeRate(done);
      if (rate !== null) {
        throughputEl.textContent = `${rate.toFixed(0)} chunks/min`;
        const remaining = total - done;
        const etaMins = remaining / rate;
        etaEl.textContent = `ETA ~${etaMins < 1 ? "<1 min" : `${Math.round(etaMins)} min`}`;
      } else {
        throughputEl.textContent = "—";
        etaEl.textContent = "ETA —";
      }
    } else {
      // extracting / scanning
      fill.className = "ai-live-pb-fill";
      const done = p.current_index;
      const total = p.total_to_process;
      const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
      labelEl.textContent = `Processing books: ${done.toLocaleString()} / ${total.toLocaleString()}`;
      pctEl.textContent = `${pct}%`;
      fill.style.width = `${pct}%`;

      const rate = computeRate(done);
      if (rate !== null) {
        throughputEl.textContent = `${rate.toFixed(1)} books/min`;
        const remaining = total - done;
        const etaMins = remaining / rate;
        etaEl.textContent = `ETA ~${etaMins < 1 ? "<1 min" : `${Math.round(etaMins)} min`}`;
      } else {
        throughputEl.textContent = "—";
        etaEl.textContent = "ETA —";
      }
    }
  }

  render(progress);

  wrapper.update = (p: IIngestionProgress): void => {
    render(p);
  };

  return wrapper;
}
