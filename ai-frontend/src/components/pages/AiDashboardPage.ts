import type { IAiApiClient } from "../../types/api";
import type { IAiStatusResponse, IIngestionProgress } from "../../types/status";
import { createAiSpinner } from "../atoms/AiSpinner";
import { createAiAlert } from "../atoms/AiAlert";
import { createAiSearchPanel } from "../organisms/AiSearchPanel";
import { createAiStatusPanel } from "../organisms/AiStatusPanel";
import { createAiIngestionControls } from "../organisms/AiIngestionControls";
import { createAiDashboardTemplate } from "../templates/AiDashboardTemplate";
import { createAiRecentFailures } from "../molecules/AiRecentFailures";
import { createAiPipelineFlow, type PipelineFlowEl } from "../organisms/AiPipelineFlow";
import { createAiLiveProgressBar, type LiveProgressBarEl } from "../molecules/AiLiveProgressBar";
import { createAiActivityFeed, type ActivityFeedEl } from "../organisms/AiActivityFeed";
import { createAiEngineHeartbeat, type HeartbeatEl } from "../atoms/AiEngineHeartbeat";
import { createPollingController, type PollingController, type PollSnapshot } from "../../utils/pollingController";
import { errorMessage } from "../../utils/result";

export class AiDashboardPage {
  private statusHolder: HTMLElement | null = null;

  // Live engine monitor elements (created in buildEngineMonitor)
  private heartbeat: HeartbeatEl | null = null;
  private pipelineFlow: PipelineFlowEl | null = null;
  private liveProgressBar: LiveProgressBarEl | null = null;
  private activityFeed: ActivityFeedEl | null = null;

  // Status panel root — we replace its contents on refresh
  private statusPanel: HTMLElement | null = null;

  private poller: PollingController | null = null;

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

  /** Unmount: cancel polling timer so no stale callbacks fire after nav. */
  public unmount(): void {
    this.poller?.stop();
    this.poller = null;
  }

  private async loadStatus(): Promise<void> {
    const holder = this.statusHolder;
    if (!holder) return;

    // Initial load: fetch status, failures, and progress in parallel
    const [statusResult, failuresResult, progressResult] = await Promise.all([
      this.client.getStatus(),
      this.client.getRecentFailures(),
      this.client.getIngestionProgress(),
    ]);

    holder.innerHTML = "";

    if (!statusResult.ok) {
      holder.appendChild(
        createAiAlert(`Could not reach sidecar: ${errorMessage(statusResult.error)}`, "danger"),
      );
      return;
    }

    const status = statusResult.data;
    const progress = progressResult.ok
      ? progressResult.data
      : { phase: "idle" as const, total_to_process: 0, current_index: 0, current_book_id: null, current_title: null, chunks_embedded_so_far: 0, chunks_total: 0 };

    const grid = document.createElement("div");
    grid.className = "ai-dashboard-grid";

    // ── Status panel (library + embedding) ──────────────────────────────────
    const sp = createAiStatusPanel(status);
    this.statusPanel = sp;
    grid.appendChild(sp);

    // ── Engine monitor panel ────────────────────────────────────────────────
    const em = this.buildEngineMonitor(status, progress);
    grid.appendChild(em);

    holder.appendChild(grid);

    // Show recent failures panel (only if there are any)
    if (failuresResult.ok && failuresResult.data.failures.length > 0) {
      const failuresEl = createAiRecentFailures(failuresResult.data.failures);
      if (failuresEl.childNodes.length > 0) {
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

    // ── Start polling ───────────────────────────────────────────────────────
    // Stop any existing poller before starting a new one (e.g. after loadStatus re-call)
    this.poller?.stop();
    this.poller = createPollingController(
      this.client,
      (snap: PollSnapshot) => { this.onPollTick(snap); },
    );
  }

  /**
   * Build the "engine monitor" panel containing:
   *  - heartbeat indicator
   *  - pipeline flow diagram
   *  - live progress bar
   *  - activity feed
   */
  private buildEngineMonitor(
    status: IAiStatusResponse,
    progress: IIngestionProgress,
  ): HTMLElement {
    const breakdown = status.library.statusBreakdown ?? {};

    const panel = document.createElement("div");
    panel.className = "panel panel-default ai-engine-monitor";

    const heading = document.createElement("div");
    heading.className = "panel-heading";
    heading.style.cssText = "display:flex;align-items:center;gap:10px;";

    const title = document.createElement("h3");
    title.className = "panel-title";
    title.style.flex = "1";
    title.textContent = "Engine Monitor";

    this.heartbeat = createAiEngineHeartbeat(progress.phase !== "idle");

    heading.appendChild(title);
    heading.appendChild(this.heartbeat);
    panel.appendChild(heading);

    const body = document.createElement("div");
    body.style.cssText = "padding:8px 12px 10px;";

    // Pipeline flow diagram
    this.pipelineFlow = createAiPipelineFlow(breakdown, progress);
    body.appendChild(this.pipelineFlow);

    // Row: progress bar (left) + activity feed (right)
    const row = document.createElement("div");
    row.className = "row";
    row.style.marginTop = "10px";

    const pbCol = document.createElement("div");
    pbCol.className = "col-sm-7";
    this.liveProgressBar = createAiLiveProgressBar(progress);
    pbCol.appendChild(this.liveProgressBar);

    const feedCol = document.createElement("div");
    feedCol.className = "col-sm-5";
    this.activityFeed = createAiActivityFeed(progress);
    feedCol.appendChild(this.activityFeed);

    row.appendChild(pbCol);
    row.appendChild(feedCol);
    body.appendChild(row);

    panel.appendChild(body);
    return panel;
  }

  /**
   * Called on every poll tick. Updates the engine monitor widgets in-place
   * (no full page rebuild) to avoid flicker. Also does a heavier status
   * panel refresh when the run finishes (phase transitions to idle from active).
   */
  private _wasActive = false;

  private onPollTick(snap: PollSnapshot): void {
    const { status, progress } = snap;
    const isActive = progress.phase !== "idle" || status.lastIngestionRun?.status === "running";

    // Update lightweight in-place elements
    this.heartbeat?.setActive(isActive);

    const breakdown = status.library.statusBreakdown ?? {};
    this.pipelineFlow?.update(breakdown, progress);
    this.liveProgressBar?.update(progress);
    this.activityFeed?.update(progress);

    // When a run just finished (active → idle), reload the full status panel
    // so the last-run stats and breakdown chart update.
    if (this._wasActive && !isActive) {
      void this.refreshStatusPanel(status);
    }

    this._wasActive = isActive;
  }

  /** Swap out just the status panel element in-place. */
  private async refreshStatusPanel(latestStatus?: IAiStatusResponse): Promise<void> {
    if (!this.statusPanel) return;
    const parent = this.statusPanel.parentElement;
    if (!parent) return;

    const statusToUse = latestStatus ?? (await this.client.getStatus().then(r => r.ok ? r.data : null));
    if (!statusToUse) return;

    const newPanel = createAiStatusPanel(statusToUse);
    parent.replaceChild(newPanel, this.statusPanel);
    this.statusPanel = newPanel;
  }
}
