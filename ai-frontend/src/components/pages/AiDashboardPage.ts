import type { IAiApiClient } from "../../types/api";
import type { IAiStatusResponse } from "../../types/status";
import { errorMessage } from "../../utils/result";
import { formatDateTime } from "../../utils/format";
import { escapeHtml } from "../../utils/dom";

export class AiDashboardPage {
  public constructor(
    private readonly container: HTMLElement,
    private readonly client: IAiApiClient,
  ) {}

  public mount(): void {
    this.container.innerHTML = `
      <div class="container-fluid ai-dashboard">
        <div class="row">
          <div class="col-sm-12">
            <h2 class="ai-dashboard__heading">AI Curated Library</h2>
          </div>
        </div>
        <div id="ai-status-panel" class="row">
          <div class="col-sm-12">
            <div class="ai-spinner">
              <span class="glyphicon glyphicon-refresh ai-spinner__icon"></span>
              Loading status&hellip;
            </div>
          </div>
        </div>
      </div>
    `;
    void this.loadStatus();
  }

  private async loadStatus(): Promise<void> {
    const panel = this.container.querySelector("#ai-status-panel");
    if (!(panel instanceof HTMLElement)) return;

    const result = await this.client.getStatus();

    if (!result.ok) {
      panel.innerHTML = `
        <div class="col-sm-12">
          <div class="alert alert-danger">
            <strong>Could not reach sidecar:</strong> ${escapeHtml(errorMessage(result.error))}
          </div>
        </div>`;
      return;
    }

    panel.innerHTML = this.renderStatus(result.data);
  }

  private renderStatus(s: IAiStatusResponse): string {
    const dbBadge = s.library.metadataDbReadable
      ? `<span class="label label-success">Readable</span>`
      : `<span class="label label-danger">Not found</span>`;

    const indexPct = s.library.bookCount > 0
      ? Math.round((s.library.indexedBookCount / s.library.bookCount) * 100)
      : 0;

    const lastRun = s.lastIngestionRun;
    const lastRunHtml = lastRun
      ? `<tr><td>Last scan</td><td>${escapeHtml(formatDateTime(lastRun.startedAt))}</td></tr>
         <tr><td>Scan status</td><td><code>${escapeHtml(lastRun.status)}</code></td></tr>
         <tr><td>Books scanned</td><td>${lastRun.scannedBooks.toLocaleString()}</td></tr>
         <tr><td>Chunks embedded</td><td>${lastRun.embeddedChunks.toLocaleString()}</td></tr>
         <tr><td>Errors</td><td>${lastRun.errorCount}</td></tr>`
      : `<tr><td colspan="2">No ingestion runs yet.</td></tr>`;

    return `
      <div class="col-sm-6">
        <div class="panel panel-default">
          <div class="panel-heading"><h3 class="panel-title">Library Index</h3></div>
          <table class="table table-condensed">
            <tbody>
              <tr><td>Calibre metadata.db</td><td>${dbBadge}</td></tr>
              <tr><td>Total books</td><td>${s.library.bookCount.toLocaleString()}</td></tr>
              <tr>
                <td>Indexed</td>
                <td>
                  ${s.library.indexedBookCount.toLocaleString()} / ${s.library.bookCount.toLocaleString()}
                  <div class="progress" style="margin:4px 0 0;height:8px">
                    <div class="progress-bar" style="width:${indexPct}%"></div>
                  </div>
                </td>
              </tr>
              <tr><td>Pending</td><td>${s.library.pendingBookCount.toLocaleString()}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="col-sm-6">
        <div class="panel panel-default">
          <div class="panel-heading"><h3 class="panel-title">Embedding &amp; Ingestion</h3></div>
          <table class="table table-condensed">
            <tbody>
              <tr><td>Provider</td><td><code>${escapeHtml(s.embedding.provider)}</code></td></tr>
              <tr><td>Model</td><td><code>${escapeHtml(s.embedding.model)}</code></td></tr>
              ${lastRunHtml}
            </tbody>
          </table>
        </div>
      </div>`;
  }
}
