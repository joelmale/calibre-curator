export function createAiBadge(percent: number): HTMLElement {
  const el = document.createElement("span");
  const cls =
    percent >= 80 ? "label-success" :
    percent >= 60 ? "label-warning" :
    "label-default";
  el.className = `label ${cls} ai-badge`;
  el.textContent = `${percent}% match`;
  return el;
}
