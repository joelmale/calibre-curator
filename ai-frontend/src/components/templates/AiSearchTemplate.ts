export function createAiSearchTemplate(searchPanel: HTMLElement): HTMLElement {
  const root = document.createElement("div");
  root.className = "container-fluid";
  root.innerHTML = `<div class="row"><div class="col-sm-12"><h2>Search Library</h2></div></div>`;
  const row = document.createElement("div");
  row.className = "row";
  const col = document.createElement("div");
  col.className = "col-sm-12";
  col.appendChild(searchPanel);
  row.appendChild(col);
  root.appendChild(row);
  return root;
}
