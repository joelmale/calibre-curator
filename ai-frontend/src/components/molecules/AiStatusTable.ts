import { escapeHtml } from "../../utils/dom";

export function createAiStatusTable(
  rows: ReadonlyArray<readonly [string, HTMLElement | string]>,
): HTMLTableElement {
  const table = document.createElement("table");
  table.className = "table table-condensed ai-status-table";

  const tbody = document.createElement("tbody");
  for (const [label, value] of rows) {
    const tr = document.createElement("tr");
    const th = document.createElement("td");
    th.textContent = label;
    const td = document.createElement("td");
    if (typeof value === "string") {
      td.innerHTML = escapeHtml(value);
    } else {
      td.appendChild(value);
    }
    tr.appendChild(th);
    tr.appendChild(td);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}
