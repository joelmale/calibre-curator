export function createAiButton(
  label: string,
  onClick: () => void,
  variant: "primary" | "default" = "primary",
): HTMLButtonElement {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = `btn btn-${variant} ai-btn`;
  btn.textContent = label;
  btn.addEventListener("click", onClick);
  return btn;
}
