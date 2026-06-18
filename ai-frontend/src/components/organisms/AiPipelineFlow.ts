/**
 * AiPipelineFlow — horizontal stage-flow diagram.
 *
 * Stages: Library → Scan → Extract → Chunk → Embed → Indexed
 * The currently-active stage (from progress.phase) is highlighted.
 * Counts at each stage are derived from statusBreakdown + progress.
 * Token colors only.
 */

import type { IIngestionProgress } from "../../types/status";

interface Stage {
  id: string;
  label: string;
  phase: string | null;  // matches PipelinePhase, or null if always-passive
  countKey: string | null;
}

const STAGES: readonly Stage[] = [
  { id: "library",   label: "Library",  phase: "scanning",   countKey: null },
  { id: "scan",      label: "Scan",     phase: "scanning",   countKey: null },
  { id: "extract",   label: "Extract",  phase: "extracting", countKey: "extracting" },
  { id: "chunk",     label: "Chunk",    phase: "extracting", countKey: "chunked" },
  { id: "embed",     label: "Embed",    phase: "embedding",  countKey: "chunked" },
  { id: "indexed",   label: "Indexed",  phase: null,         countKey: "indexed" },
];

export interface PipelineFlowEl extends HTMLElement {
  /** Update the display without recreating the DOM tree. */
  update(breakdown: Readonly<Record<string, number>>, progress: IIngestionProgress): void;
}

function countForStage(
  stage: Stage,
  breakdown: Readonly<Record<string, number>>,
  progress: IIngestionProgress,
): string {
  if (stage.id === "library") {
    // Total books known to calibre — derive from breakdown sum
    const total = Object.values(breakdown).reduce((a, b) => a + b, 0);
    return total > 0 ? total.toLocaleString() : "";
  }
  if (stage.id === "scan") {
    return progress.total_to_process > 0
      ? `${progress.current_index}/${progress.total_to_process}`
      : "";
  }
  if (stage.id === "embed") {
    return progress.chunks_total > 0
      ? `${progress.chunks_embedded_so_far}/${progress.chunks_total} chunks`
      : "";
  }
  if (stage.countKey) {
    const n = breakdown[stage.countKey] ?? 0;
    return n > 0 ? n.toLocaleString() : "";
  }
  return "";
}

function isStageActive(stage: Stage, progress: IIngestionProgress): boolean {
  if (!stage.phase || progress.phase === "idle") return false;
  return stage.phase === progress.phase;
}

let _styleInjected = false;
function injectStyles(): void {
  if (_styleInjected) return;
  _styleInjected = true;
  const style = document.createElement("style");
  style.textContent = `
    .ai-pipeline-flow {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 0;
      padding: 10px 0 6px;
      overflow-x: auto;
    }
    .ai-pipeline-stage {
      display: flex;
      flex-direction: column;
      align-items: center;
      min-width: 64px;
      padding: 6px 8px;
      border-radius: var(--ai-radius, 4px);
      border: 1px solid transparent;
      transition: background 0.2s, border-color 0.2s;
      cursor: default;
    }
    .ai-pipeline-stage.active {
      background: var(--ai-color-info-bg);
      border-color: var(--ai-color-info-border);
    }
    .ai-pipeline-stage-label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.4px;
      color: var(--ai-color-text-muted);
    }
    .ai-pipeline-stage.active .ai-pipeline-stage-label {
      color: var(--ai-color-info);
    }
    .ai-pipeline-stage-count {
      font-size: 11px;
      color: var(--ai-color-text);
      margin-top: 2px;
      white-space: nowrap;
    }
    .ai-pipeline-stage.active .ai-pipeline-stage-count {
      color: var(--ai-color-info);
      font-weight: 600;
    }
    .ai-pipeline-arrow {
      color: var(--ai-color-border-strong);
      font-size: 14px;
      padding: 0 2px;
      flex-shrink: 0;
      user-select: none;
    }
    .ai-pipeline-stage-failed {
      display: inline-block;
      margin-top: 2px;
      font-size: 10px;
      padding: 1px 4px;
      border-radius: 3px;
      background: var(--ai-color-danger-bg);
      color: var(--ai-color-danger);
      border: 1px solid var(--ai-color-danger-border);
    }
  `;
  document.head.appendChild(style);
}

export function createAiPipelineFlow(
  breakdown: Readonly<Record<string, number>>,
  progress: IIngestionProgress,
): PipelineFlowEl {
  injectStyles();

  const wrapper = document.createElement("div") as unknown as PipelineFlowEl;
  wrapper.className = "ai-pipeline-flow";

  // Build stage cells with arrows between them
  const stageCells: HTMLElement[] = [];

  STAGES.forEach((stage, idx) => {
    const cell = document.createElement("div");
    cell.className = `ai-pipeline-stage${isStageActive(stage, progress) ? " active" : ""}`;
    cell.dataset["stageId"] = stage.id;

    const labelEl = document.createElement("div");
    labelEl.className = "ai-pipeline-stage-label";
    labelEl.textContent = stage.label;
    cell.appendChild(labelEl);

    const countEl = document.createElement("div");
    countEl.className = "ai-pipeline-stage-count";
    countEl.textContent = countForStage(stage, breakdown, progress);
    cell.appendChild(countEl);

    // Failed chip — only on the "indexed" stage position we show failed count
    if (stage.id === "indexed" && (breakdown["failed"] ?? 0) > 0) {
      const failedChip = document.createElement("span");
      failedChip.className = "ai-pipeline-stage-failed";
      failedChip.textContent = `${(breakdown["failed"] ?? 0).toLocaleString()} failed`;
      cell.appendChild(failedChip);
    }

    stageCells.push(cell);
    wrapper.appendChild(cell);

    // Arrow between stages (not after last)
    if (idx < STAGES.length - 1) {
      const arrow = document.createElement("span");
      arrow.className = "ai-pipeline-arrow";
      arrow.textContent = "›";
      wrapper.appendChild(arrow);
    }
  });

  wrapper.update = (
    newBreakdown: Readonly<Record<string, number>>,
    newProgress: IIngestionProgress,
  ): void => {
    stageCells.forEach((cell, idx) => {
      const stage = STAGES[idx]!;
      const active = isStageActive(stage, newProgress);

      // Toggle active class
      if (active) {
        cell.classList.add("active");
      } else {
        cell.classList.remove("active");
      }

      // Update count
      const countEl = cell.querySelector(".ai-pipeline-stage-count");
      if (countEl) {
        countEl.textContent = countForStage(stage, newBreakdown, newProgress);
      }

      // Update failed chip visibility
      if (stage.id === "indexed") {
        let chip = cell.querySelector<HTMLElement>(".ai-pipeline-stage-failed");
        const failedCount = newBreakdown["failed"] ?? 0;
        if (failedCount > 0) {
          if (!chip) {
            chip = document.createElement("span");
            chip.className = "ai-pipeline-stage-failed";
            cell.appendChild(chip);
          }
          chip.textContent = `${failedCount.toLocaleString()} failed`;
        } else if (chip) {
          chip.remove();
        }
      }
    });
  };

  return wrapper;
}
