import type { IAiApiClient } from "../../types/api";
import { createAiSearchBar } from "../molecules/AiSearchBar";
import { createAiBookList } from "../molecules/AiBookList";
import { createAiSpinner } from "../atoms/AiSpinner";
import { createAiAlert } from "../atoms/AiAlert";
import { createAiEmptyState } from "../molecules/AiEmptyState";
import { errorMessage } from "../../utils/result";
import { escapeHtml } from "../../utils/dom";

export function createAiSearchPanel(client: IAiApiClient): HTMLElement {
  const panel = document.createElement("div");
  panel.className = "ai-search-panel";

  const results = document.createElement("div");
  results.className = "ai-search-panel__results";
  results.style.marginTop = "16px";

  async function doSearch(query: string): Promise<void> {
    results.innerHTML = "";
    results.appendChild(createAiSpinner("Searching…"));

    const res = await client.searchSemantic({ query, limit: 12 });
    results.innerHTML = "";

    if (!res.ok) {
      results.appendChild(createAiAlert(errorMessage(res.error), "danger"));
      return;
    }
    if (res.data.results.length === 0) {
      results.appendChild(
        createAiEmptyState(`No results for "${escapeHtml(query)}".`),
      );
      return;
    }

    const heading = document.createElement("h4");
    heading.textContent = `Results for "${query}"`;
    heading.style.marginBottom = "12px";
    results.appendChild(heading);
    results.appendChild(createAiBookList(res.data.results));
  }

  panel.appendChild(createAiSearchBar(doSearch));
  panel.appendChild(results);
  return panel;
}
