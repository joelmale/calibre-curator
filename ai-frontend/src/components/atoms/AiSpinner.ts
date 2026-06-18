export function createAiSpinner(label = "Loading…"): HTMLElement {
  const el = document.createElement("div");
  el.className = "ai-spinner";
  el.setAttribute("role", "status");
  el.setAttribute("aria-label", label);
  el.innerHTML = `<span class="glyphicon glyphicon-refresh ai-spinner__icon" aria-hidden="true"></span> ${label}`;
  return el;
}
