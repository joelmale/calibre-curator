import type { IAiApiClient } from "../../types/api";
import { createAiSearchPanel } from "../organisms/AiSearchPanel";
import { createAiSearchTemplate } from "../templates/AiSearchTemplate";

export class AiSearchPage {
  public constructor(
    private readonly container: HTMLElement,
    private readonly client: IAiApiClient,
  ) {}

  public mount(): void {
    this.container.innerHTML = "";
    this.container.appendChild(
      createAiSearchTemplate(createAiSearchPanel(this.client)),
    );
  }
}
