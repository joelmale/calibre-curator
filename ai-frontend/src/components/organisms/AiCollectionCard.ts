import type { ICuratedCollectionSummary } from "../../types/collection";
import { escapeHtml } from "../../utils/dom";
import { formatDateTime } from "../../utils/format";

export function createAiCollectionCard(
  summary: ICuratedCollectionSummary,
): HTMLElement {
  const card = document.createElement("div");
  card.className = "panel panel-default ai-collection-card";

  card.innerHTML = `
    <div class="panel-heading">
      <h4 class="panel-title">${escapeHtml(summary.title)}</h4>
    </div>
    <div class="panel-body">
      <p>${escapeHtml(summary.description)}</p>
      <p class="text-muted" style="font-size:12px">
        ${summary.itemCount} book${summary.itemCount === 1 ? "" : "s"}
        &middot; Updated ${escapeHtml(formatDateTime(summary.updatedAt))}
      </p>
    </div>`;

  return card;
}
