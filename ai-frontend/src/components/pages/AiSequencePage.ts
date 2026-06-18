import type { IAiApiClient } from "../../types/api";
import { createAiSequencePanel } from "../organisms/AiSequencePanel";

export class AiSequencePage {
  public constructor(
    private readonly container: HTMLElement,
    private readonly client: IAiApiClient,
  ) {}

  public mount(): void {
    const root = document.createElement("div");
    root.className = "container-fluid ai-sequence";
    root.innerHTML =
      `<div class="row"><div class="col-sm-12">` +
      `<h2>Reading Sequence Builder</h2>` +
      `<p class="text-muted">Give a goal — the curator finds candidates in your library and orders them into a reading path.</p>` +
      `</div></div>`;

    const row = document.createElement("div");
    row.className = "row";
    const col = document.createElement("div");
    col.className = "col-sm-12";
    col.appendChild(createAiSequencePanel(this.client));
    row.appendChild(col);
    root.appendChild(row);

    this.container.innerHTML = "";
    this.container.appendChild(root);
  }
}
