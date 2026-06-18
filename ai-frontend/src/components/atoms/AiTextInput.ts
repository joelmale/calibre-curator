export function createAiTextInput(options: {
  placeholder?: string;
  ariaLabel?: string;
  id?: string;
}): HTMLInputElement {
  const input = document.createElement("input");
  input.type = "text";
  input.className = "form-control ai-text-input";
  if (options.placeholder !== undefined) input.placeholder = options.placeholder;
  if (options.ariaLabel !== undefined) input.setAttribute("aria-label", options.ariaLabel);
  if (options.id !== undefined) input.id = options.id;
  return input;
}
