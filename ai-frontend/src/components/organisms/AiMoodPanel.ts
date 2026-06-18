import type { IAiApiClient } from "../../types/api";
import { createAiBookList } from "../molecules/AiBookList";
import { createAiSpinner } from "../atoms/AiSpinner";
import { createAiAlert } from "../atoms/AiAlert";
import { createAiEmptyState } from "../molecules/AiEmptyState";
import { createAiIndexCoverageBanner } from "../molecules/AiIndexCoverageBanner";
import { errorMessage } from "../../utils/result";
import { escapeHtml } from "../../utils/dom";

export function createAiMoodPanel(client: IAiApiClient): HTMLElement {
  const panel = document.createElement("div");
  panel.className = "ai-mood-panel";

  const form = document.createElement("form");
  form.className = "ai-mood-form";

  const textarea = document.createElement("textarea");
  textarea.className = "form-control";
  textarea.rows = 3;
  textarea.placeholder =
    "Describe what you're in the mood for… e.g. “a dark, fast-paced political thriller, nothing too technical”";
  textarea.setAttribute("aria-label", "Describe your reading mood");

  const btn = document.createElement("button");
  btn.type = "submit";
  btn.className = "btn btn-primary";
  btn.textContent = "Find books";
  btn.style.marginTop = "8px";

  form.appendChild(textarea);
  form.appendChild(btn);

  const output = document.createElement("div");
  output.style.marginTop = "16px";

  async function run(prompt: string): Promise<void> {
    output.innerHTML = "";
    output.appendChild(createAiSpinner("Interpreting your mood…"));
    btn.disabled = true;

    const res = await client.searchMood({ prompt });
    btn.disabled = false;
    output.innerHTML = "";

    if (!res.ok) {
      output.appendChild(createAiAlert(errorMessage(res.error), "danger"));
      return;
    }

    // Show index-coverage notice when the index isn't fully built yet.
    const banner = createAiIndexCoverageBanner(res.data.indexCoverage);
    if (banner) output.appendChild(banner);

    // Always show the curator explanation (honest no-match text comes from backend).
    if (res.data.explanation) {
      const card = document.createElement("div");
      // Use warning style for no-match (results empty), info style for matches found.
      const panelStyle = res.data.results.length === 0 ? "panel-warning" : "panel-info";
      card.className = `panel ${panelStyle}`;
      card.innerHTML =
        `<div class="panel-body"><strong>Curator:</strong> ${escapeHtml(res.data.explanation)}` +
        (res.data.results.length > 0 && res.data.semanticQuery
          ? `<br><small class="text-muted">Searched for: ${escapeHtml(res.data.semanticQuery)}</small>`
          : "") +
        `</div>`;
      output.appendChild(card);
    }

    if (res.data.results.length === 0) {
      output.appendChild(createAiEmptyState("Try rephrasing your mood, or check back as more books are indexed."));
      return;
    }
    output.appendChild(createAiBookList(res.data.results));
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const prompt = textarea.value.trim();
    if (prompt) void run(prompt);
  });

  panel.appendChild(form);
  panel.appendChild(output);
  return panel;
}
