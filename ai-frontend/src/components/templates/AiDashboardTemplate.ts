export function createAiDashboardTemplate(options: {
  heading: string;
  search: HTMLElement;
  status: HTMLElement;
}): HTMLElement {
  const root = document.createElement("div");
  root.className = "container-fluid ai-dashboard";

  const headingRow = document.createElement("div");
  headingRow.className = "row";
  headingRow.innerHTML = `<div class="col-sm-12"><h2 class="ai-dashboard__heading">${options.heading}</h2></div>`;

  const searchRow = document.createElement("div");
  searchRow.className = "row";
  const searchCol = document.createElement("div");
  searchCol.className = "col-sm-12";
  searchCol.appendChild(options.search);
  searchRow.appendChild(searchCol);

  const statusRow = document.createElement("div");
  statusRow.className = "row";
  statusRow.style.marginTop = "24px";
  const statusCol = document.createElement("div");
  statusCol.className = "col-sm-12";
  statusCol.appendChild(options.status);
  statusRow.appendChild(statusCol);

  root.appendChild(headingRow);
  root.appendChild(searchRow);
  root.appendChild(statusRow);
  return root;
}
