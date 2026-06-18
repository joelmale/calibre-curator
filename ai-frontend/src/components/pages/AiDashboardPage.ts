import type { IAiApiClient } from "../../types/api";
import { createAiSpinner } from "../atoms/AiSpinner";
import { createAiAlert } from "../atoms/AiAlert";
import { createAiSearchPanel } from "../organisms/AiSearchPanel";
import { createAiStatusPanel } from "../organisms/AiStatusPanel";
import { createAiIngestionControls } from "../organisms/AiIngestionControls";
import { createAiDashboardTemplate } from "../templates/AiDashboardTemplate";
import { errorMessage } from "../../utils/result";

export class AiDashboardPage {
  private statusHolder: HTMLElement | null = null;

  public constructor(
    private readonly container: HTMLElement,
    private readonly client: IAiApiClient,
  ) {}

  public mount(): void {
    const statusHolder = document.createElement("div");
    this.statusHolder = statusHolder;
    statusHolder.appendChild(createAiSpinner("Loading library status…"));

    const tpl = createAiDashboardTemplate({
      heading: "AI Curated Library",
      search: createAiSearchPanel(this.client),
      status: statusHolder,
    });

    this.container.innerHTML = "";
    this.container.appendChild(tpl);

    void this.loadStatus();
  }

  private async loadStatus(): Promise<void> {
    const holder = this.statusHolder;
    if (!holder) return;

    const result = await this.client.getStatus();
    holder.innerHTML = "";

    if (!result.ok) {
      holder.appendChild(
        createAiAlert(`Could not reach sidecar: ${errorMessage(result.error)}`, "danger"),
      );
      return;
    }

    holder.appendChild(createAiStatusPanel(result.data));
    holder.appendChild(
      createAiIngestionControls(this.client, () => {
        // Refresh status 3 s after triggering so the new run row appears
        setTimeout(() => { void this.loadStatus(); }, 3000);
      }),
    );
  }
}
