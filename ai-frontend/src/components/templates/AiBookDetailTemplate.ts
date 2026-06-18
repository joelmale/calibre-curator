export function createAiBookDetailTemplate(options: {
  title: string;
  shelf: HTMLElement;
}): HTMLElement {
  const root = document.createElement("div");
  root.className = "container-fluid";
  root.innerHTML = `<div class="row"><div class="col-sm-12"><h2>${options.title}</h2></div></div>`;
  const row = document.createElement("div");
  row.className = "row";
  const col = document.createElement("div");
  col.className = "col-sm-12";
  col.appendChild(options.shelf);
  row.appendChild(col);
  root.appendChild(row);
  return root;
}
