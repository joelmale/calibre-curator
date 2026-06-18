export function createAiProgressBar(percent: number): HTMLElement {
  const clamped = Math.max(0, Math.min(100, Math.round(percent)));
  const wrapper = document.createElement("div");
  wrapper.className = "progress ai-progress-bar";
  wrapper.style.marginTop = "4px";
  wrapper.style.height = "8px";
  wrapper.innerHTML = `<div class="progress-bar" role="progressbar"
    aria-valuenow="${clamped}" aria-valuemin="0" aria-valuemax="100"
    style="width:${clamped}%"></div>`;
  return wrapper;
}
