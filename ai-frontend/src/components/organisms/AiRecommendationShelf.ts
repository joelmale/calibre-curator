import type { IAiApiClient } from "../../types/api";
import { createAiBookList } from "../molecules/AiBookList";
import { createAiSpinner } from "../atoms/AiSpinner";
import { createAiAlert } from "../atoms/AiAlert";
import { createAiEmptyState } from "../molecules/AiEmptyState";
import { errorMessage } from "../../utils/result";

export function createAiRecommendationShelf(
  client: IAiApiClient,
  bookId: number,
  title = "Similar Books",
  limit = 6,
): HTMLElement {
  const shelf = document.createElement("div");
  shelf.className = "ai-recommendation-shelf";

  const header = document.createElement("h3");
  header.className = "ai-recommendation-shelf__header";
  header.textContent = title;

  const body = document.createElement("div");
  body.className = "ai-recommendation-shelf__body";
  body.appendChild(createAiSpinner("Finding similar books…"));

  shelf.appendChild(header);
  shelf.appendChild(body);

  void (async () => {
    const res = await client.getBookRecommendations(bookId, limit);
    body.innerHTML = "";

    if (!res.ok) {
      body.appendChild(createAiAlert(errorMessage(res.error), "warning"));
      return;
    }
    if (res.data.recommendations.length === 0) {
      body.appendChild(createAiEmptyState("No recommendations yet — index more books first."));
      return;
    }
    body.appendChild(createAiBookList(res.data.recommendations));
  })();

  return shelf;
}
