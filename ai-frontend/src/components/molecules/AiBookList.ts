import type { IApiBookResult } from "../../types/api";
import { createAiBookCard } from "./AiBookCard";

export function createAiBookList(books: readonly IApiBookResult[]): HTMLElement {
  const grid = document.createElement("div");
  grid.className = "row ai-book-list";

  for (const book of books) {
    const col = document.createElement("div");
    col.className = "col-xs-12 col-sm-6 col-md-4";
    col.style.marginBottom = "16px";
    col.appendChild(createAiBookCard(book));
    grid.appendChild(col);
  }

  return grid;
}
