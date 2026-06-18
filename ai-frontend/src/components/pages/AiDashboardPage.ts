import type { IAiApiClient } from "../../types/api";
import { createAiSpinner } from "../atoms/AiSpinner";
import { createAiAlert } from "../atoms/AiAlert";
import { createAiSearchPanel } from "../organisms/AiSearchPanel";
import { createAiStatusPanel } from "../organisms/AiStatusPanel";
import { createAiIngestionControls } from "../organisms/AiIngestionControls";
import { createAiDashboardTemplate } from "../templates/AiDashboardTemplate";
import { createAiRecentFailures } from "../molecules/AiRecentFailures";
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

    // Fetch status and failures in parallel
    const [statusResult, failuresResult] = await Promise.all([
      this.client.getStatus(),
      this.client.getRecentFailures(),
    ]);

    holder.innerHTML = "";

    if (!statusResult.ok) {
      holder.appendChild(
        createAiAlert(`Could not reach sidecar: ${errorMessage(statusResult.error)}`, "danger"),
      );
      return;
    }

    holder.appendChild(createAiStatusPanel(statusResult.data));

    // Show recent failures panel (only if there are any)
    if (failuresResult.ok && failuresResult.data.failures.length > 0) {
      const failuresEl = createAiRecentFailures(failuresResult.data.failures);
      if (failuresEl.childNodes.length > 0) {
        // Wrap in a row so it aligns with the status panel columns
        const row = document.createElement("div");
        row.className = "row";
        const col = document.createElement("div");
        col.className = "col-sm-12";
        col.appendChild(failuresEl);
        row.appendChild(col);
        holder.appendChild(row);
      }
    }

    holder.appendChild(
      createAiIngestionControls(this.client, () => {
        // Refresh status 3 s after triggering so the new run row appears
        setTimeout(() => { void this.loadStatus(); }, 3000);
      }),
    );
  }
}
