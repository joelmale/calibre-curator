/**
 * AiActivityFeed — live feed of recently processed books.
 *
 * - Shows "Now: [idx/total] <current_title>" during active run
 * - Keeps a rolling list of last ~8 items seen across polls (client-side)
 * - Shows "No active run" when idle
 * - Token colors only
 */

import type { IIngestionProgress } from "../../types/status";

const MAX_HISTORY = 8;

let _styleInjected = false;
function injectStyles(): void {
  if (_styleInjected) return;
  _styleInjected = true;
  const style = document.createElement("style");
  style.textContent = `
    .ai-activity-feed {
      font-size: 12px;
    }
    .ai-activity-feed-now {
      display: flex;
      align-items: baseline;
      gap: 6px;
      padding: 4px 0;
      border-bottom: 1px solid var(--ai-color-border);
      margin-bottom: 6px;
    }
    .ai-activity-feed-now-badge {
      font-size: 10px;
      font-weight: 700;
      padding: 1px 5px;
      border-radius: 3px;
      background: var(--ai-color-info-bg);
      color: var(--ai-color-info);
      border: 1px solid var(--ai-color-info-border);
      white-space: nowrap;
      flex-shrink: 0;
    }
    .ai-activity-feed-now-title {
      color: var(--ai-color-text);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .ai-activity-feed-history {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 3px;
    }
    .ai-activity-feed-item {
      display: flex;
      align-items: baseline;
      gap: 6px;
      color: var(--ai-color-text-muted);
      overflow: hidden;
    }
    .ai-activity-feed-item-pos {
      flex-shrink: 0;
      font-variant-numeric: tabular-nums;
      min-width: 36px;
      text-align: right;
    }
    .ai-activity-feed-item-title {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .ai-activity-feed-idle {
      color: var(--ai-color-text-muted);
      font-style: italic;
      padding: 4px 0;
    }
  `;
  document.head.appendChild(style);
}

interface HistoryItem {
  index: number;
  total: number;
  title: string;
  bookId: number;
}

export interface ActivityFeedEl extends HTMLElement {
  update(progress: IIngestionProgress): void;
}

export function createAiActivityFeed(progress: IIngestionProgress): ActivityFeedEl {
  injectStyles();

  const history: HistoryItem[] = [];
  let lastSeenBookId: number | null = null;

  const wrapper = document.createElement("div") as unknown as ActivityFeedEl;
  wrapper.className = "ai-activity-feed";

  // "Now" row
  const nowRow = document.createElement("div");
  nowRow.className = "ai-activity-feed-now";

  const nowBadge = document.createElement("span");
  nowBadge.className = "ai-activity-feed-now-badge";
  nowBadge.textContent = "NOW";

  const nowTitle = document.createElement("span");
  nowTitle.className = "ai-activity-feed-now-title";

  nowRow.appendChild(nowBadge);
  nowRow.appendChild(nowTitle);

  // History list
  const histList = document.createElement("ul");
  histList.className = "ai-activity-feed-history";

  // Idle message
  const idleMsg = document.createElement("div");
  idleMsg.className = "ai-activity-feed-idle";
  idleMsg.textContent = "No active run";

  wrapper.appendChild(idleMsg);
  wrapper.appendChild(nowRow);
  wrapper.appendChild(histList);

  function maybeAddToHistory(p: IIngestionProgress): void {
    if (
      p.current_book_id !== null &&
      p.current_book_id !== lastSeenBookId &&
      p.current_title
    ) {
      lastSeenBookId = p.current_book_id;
      history.unshift({
        index:  p.current_index,
        total:  p.total_to_process,
        title:  p.current_title,
        bookId: p.current_book_id,
      });
      if (history.length > MAX_HISTORY) history.pop();
    }
  }

  function renderHistory(): void {
    histList.innerHTML = "";
    history.forEach((item) => {
      const li = document.createElement("li");
      li.className = "ai-activity-feed-item";

      const pos = document.createElement("span");
      pos.className = "ai-activity-feed-item-pos";
      pos.textContent = `${item.index}/${item.total}`;

      const title = document.createElement("span");
      title.className = "ai-activity-feed-item-title";
      title.textContent = item.title;
      title.title = item.title;

      li.appendChild(pos);
      li.appendChild(title);
      histList.appendChild(li);
    });
  }

  function render(p: IIngestionProgress): void {
    const isActive = p.phase !== "idle";
    idleMsg.style.display = isActive ? "none" : "";
    nowRow.style.display = isActive ? "" : "none";
    histList.style.display = isActive && history.length > 0 ? "" : "none";

    if (!isActive) return;

    maybeAddToHistory(p);

    if (p.phase === "embedding") {
      nowBadge.textContent = "EMBED";
      nowTitle.textContent = p.chunks_total > 0
        ? `${p.chunks_embedded_so_far.toLocaleString()} / ${p.chunks_total.toLocaleString()} chunks embedded`
        : "Embedding…";
    } else if (p.current_title) {
      nowBadge.textContent = `${p.current_index}/${p.total_to_process}`;
      nowTitle.textContent = p.current_title;
      nowTitle.title = p.current_title;
    } else {
      nowBadge.textContent = "SCAN";
      nowTitle.textContent = "Scanning library…";
    }

    renderHistory();
  }

  render(progress);

  wrapper.update = (p: IIngestionProgress): void => {
    render(p);
  };

  return wrapper;
}
