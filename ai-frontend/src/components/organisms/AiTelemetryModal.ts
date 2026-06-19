import { createAiStatusTable } from "../molecules/AiStatusTable";
import { formatPercent } from "../../utils/format";

export function initTelemetryModal(apiBaseUrl: string) {
  // If already initialized, do nothing
  if (document.getElementById("ai-telemetry-modal")) return;

  const modalHtml = `
    <div class="modal fade" id="ai-telemetry-modal" tabindex="-1" role="dialog" aria-labelledby="aiTelemetryModalLabel">
      <div class="modal-dialog modal-lg" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <button type="button" class="close" data-dismiss="modal" aria-label="Close"><span aria-hidden="true">&times;</span></button>
            <h4 class="modal-title" id="aiTelemetryModalLabel">AI Telemetry Dashboard</h4>
          </div>
          <div class="modal-body" id="ai-telemetry-body" style="min-height: 200px;">
            <p class="text-muted">Loading telemetry data...</p>
          </div>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);

  const btn = document.getElementById("ai-telemetry-btn");
  if (btn) {
    btn.addEventListener("click", () => {
      fetchTelemetry(apiBaseUrl);
    });
  }
}

async function fetchTelemetry(apiBaseUrl: string) {
  const body = document.getElementById("ai-telemetry-body");
  if (!body) return;

  try {
    body.innerHTML = '<p class="text-muted">Loading telemetry data...</p>';
    const res = await fetch(`${apiBaseUrl}/status/telemetry`);
    if (!res.ok) throw new Error("Failed to load telemetry");
    
    const data = await res.json();
    const stats = data.stats || [];

    if (stats.length === 0) {
      body.innerHTML = '<p class="text-muted">No API requests have been logged yet.</p>';
      return;
    }

    body.innerHTML = "";
    
    const tableRows = stats.map((row: any) => {
      const avgTokens = Math.round((row.total_prompt_tokens + row.total_completion_tokens) / row.total_requests);
      const errorRate = formatPercent(row.error_requests / row.total_requests);
      
      const badgeClass = row.error_requests > 0 ? "label-danger" : "label-success";
      const errorBadge = `<span class="label ${badgeClass}">${errorRate} Errors</span>`;

      return [
        `<strong>${row.provider}</strong><br><small class="text-muted">${row.model}</small>`,
        row.endpoint_type,
        row.total_requests.toLocaleString(),
        `${row.total_prompt_tokens.toLocaleString()} / ${row.total_completion_tokens.toLocaleString()}`,
        `${Math.round(row.avg_duration_ms)}ms`,
        `${row.min_duration_ms}ms / ${row.max_duration_ms}ms`,
        errorBadge
      ];
    });

    const thead = document.createElement("thead");
    thead.innerHTML = `
      <tr>
        <th>Provider / Model</th>
        <th>Type</th>
        <th>Calls</th>
        <th>Tokens (In/Out)</th>
        <th>Avg Time</th>
        <th>Min / Max Time</th>
        <th>Errors</th>
      </tr>
    `;

    const table = document.createElement("table");
    table.className = "table table-striped table-hover";
    table.style.fontSize = "12px";
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    tableRows.forEach((row: any[]) => {
      const tr = document.createElement("tr");
      row.forEach(cellHtml => {
        const td = document.createElement("td");
        td.innerHTML = String(cellHtml);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    body.appendChild(table);

  } catch (err) {
    body.innerHTML = `<p class="text-danger">Error loading telemetry: ${err}</p>`;
  }
}
