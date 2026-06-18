import type { IAiApiClient } from "../../types/api";
import { createAiMoodPanel } from "../organisms/AiMoodPanel";

export class AiMoodPage {
  public constructor(
    private readonly container: HTMLElement,
    private readonly client: IAiApiClient,
  ) {}

  public mount(): void {
    const root = document.createElement("div");
    root.className = "container-fluid ai-mood";
    root.innerHTML =
      `<div class="row"><div class="col-sm-12">` +
      `<h2>Reading Mood Wizard</h2>` +
      `<p class="text-muted">Tell the curator how you feel — it translates that into a search and ranks your library.</p>` +
      `</div></div>`;

    const row = document.createElement("div");
    row.className = "row";
    const col = document.createElement("div");
    col.className = "col-sm-12";
    col.appendChild(createAiMoodPanel(this.client));
    row.appendChild(col);
    root.appendChild(row);

    this.container.innerHTML = "";
    this.container.appendChild(root);
  }
}
