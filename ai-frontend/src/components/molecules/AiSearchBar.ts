import { createAiTextInput } from "../atoms/AiTextInput";

export function createAiSearchBar(onSearch: (query: string) => void): HTMLElement {
  const form = document.createElement("form");
  form.className = "ai-search-bar";

  const group = document.createElement("div");
  group.className = "input-group";

  const input = createAiTextInput({
    placeholder: "Search by theme, mood, concept…",
    ariaLabel: "Semantic search",
  });

  const btnSpan = document.createElement("span");
  btnSpan.className = "input-group-btn";

  const btn = document.createElement("button");
  btn.type = "submit";
  btn.className = "btn btn-primary";
  btn.textContent = "Search";

  btnSpan.appendChild(btn);
  group.appendChild(input);
  group.appendChild(btnSpan);
  form.appendChild(group);

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = input.value.trim();
    if (query) onSearch(query);
  });

  return form;
}
