import type { IApiBookResult } from "../../types/api";
import { escapeHtml } from "../../utils/dom";
import { createAiBadge } from "../atoms/AiBadge";

export function createAiBookCard(book: IApiBookResult): HTMLElement {
  const card = document.createElement("div");
  card.className = "ai-book-card";

  const authors = book.authors.map(escapeHtml).join(", ");
  const reasons = book.matchReasons
    .map((r) => `<li>${escapeHtml(r)}</li>`)
    .join("");

  const body = document.createElement("div");
  body.className = "ai-book-card__body";
  body.innerHTML = `
    <h4 class="ai-book-card__title">${escapeHtml(book.title)}</h4>
    <p class="ai-book-card__authors">${authors}</p>
    <ul class="ai-match-reasons">${reasons}</ul>`;

  body.prepend(createAiBadge(book.matchPercent));
  card.appendChild(body);
  return card;
}
