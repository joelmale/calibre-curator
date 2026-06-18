import type { IAiApiClient } from "../../types/api";
import { createAiRecommendationShelf } from "../organisms/AiRecommendationShelf";
import { createAiBookDetailTemplate } from "../templates/AiBookDetailTemplate";

export class AiBookDetailPage {
  public constructor(
    private readonly container: HTMLElement,
    private readonly client: IAiApiClient,
  ) {}

  public mount(bookId: number, bookTitle: string): void {
    this.container.innerHTML = "";
    this.container.appendChild(
      createAiBookDetailTemplate({
        title: bookTitle,
        shelf: createAiRecommendationShelf(this.client, bookId),
      }),
    );
  }
}
