import type { IIndexCoverage } from "../../types/api";
import { escapeHtml } from "../../utils/dom";

/**
 * Returns a small informational banner when the vector index is not yet
 * complete, so users understand why results may be limited.
 * Returns null when coverage is 100% or unknown (no banner shown).
 */
export function createAiIndexCoverageBanner(
  coverage: IIndexCoverage | undefined,
): HTMLElement | null {
  if (!coverage) return null;
  const { indexedBookCount, totalBooks } = coverage;
  if (totalBooks <= 0 || indexedBookCount >= totalBooks) return null;

  const pct = Math.round((indexedBookCount / totalBooks) * 100);
  const el = document.createElement("div");
  el.className = "ai-index-coverage-banner";
  el.style.cssText = [
    "padding: 6px 10px",
    "margin-top: 8px",
    "border-radius: 4px",
    "font-size: 0.85em",
    "color: var(--ai-color-text-muted, inherit)",
    "background: var(--ai-color-surface-alt, rgba(0,0,0,0.04))",
    "border-left: 3px solid var(--ai-color-accent, #6c757d)",
  ].join(";");
  el.innerHTML =
    `Search currently covers <strong>${escapeHtml(String(indexedBookCount))}</strong> of ` +
    `<strong>${escapeHtml(String(totalBooks))}</strong> books (${escapeHtml(String(pct))}% indexed ` +
    `— indexing in progress). Results will improve as indexing completes.`;
  return el;
}
