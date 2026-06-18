import type { IAiApiClient } from "../../types/api";
import { createAiCollectionCard } from "../organisms/AiCollectionCard";
import { createAiCollectionsTemplate } from "../templates/AiCollectionsTemplate";
import { createAiSpinner } from "../atoms/AiSpinner";
import { createAiAlert } from "../atoms/AiAlert";
import { createAiEmptyState } from "../molecules/AiEmptyState";
import { errorMessage } from "../../utils/result";

export class AiCollectionsPage {
  public constructor(
    private readonly container: HTMLElement,
    private readonly client: IAiApiClient,
  ) {}

  public mount(): void {
    const content = document.createElement("div");
    content.appendChild(createAiSpinner("Loading collections…"));

    this.container.innerHTML = "";
    this.container.appendChild(createAiCollectionsTemplate(content));

    void this.load(content);
  }

  private async load(content: HTMLElement): Promise<void> {
    const res = await this.client.listCollections();
    content.innerHTML = "";

    if (!res.ok) {
      content.appendChild(createAiAlert(errorMessage(res.error), "danger"));
      return;
    }
    if (res.data.collections.length === 0) {
      content.appendChild(createAiEmptyState("No curated collections yet."));
      return;
    }
    for (const summary of res.data.collections) {
      content.appendChild(createAiCollectionCard(summary));
    }
  }
}
