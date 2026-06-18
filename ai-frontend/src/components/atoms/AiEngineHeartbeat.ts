/**
 * AiEngineHeartbeat — small pulsing status indicator.
 * Shows "● indexing…" when active, "idle" when not.
 * Token colors only; uses a CSS keyframe injected once.
 */

let _styleInjected = false;

function injectStyles(): void {
  if (_styleInjected) return;
  _styleInjected = true;
  const style = document.createElement("style");
  style.textContent = `
    @keyframes ai-heartbeat-pulse {
      0%, 100% { opacity: 1; }
      50%       { opacity: 0.3; }
    }
    .ai-heartbeat-dot {
      animation: ai-heartbeat-pulse 1.2s ease-in-out infinite;
    }
  `;
  document.head.appendChild(style);
}

export interface HeartbeatEl extends HTMLElement {
  /** Update active state in-place without recreating the element. */
  setActive(active: boolean): void;
}

export function createAiEngineHeartbeat(active: boolean): HeartbeatEl {
  injectStyles();

  const wrapper = document.createElement("span") as HeartbeatEl;
  wrapper.className = "ai-engine-heartbeat";
  wrapper.style.cssText = "display:inline-flex;align-items:center;gap:5px;font-size:12px;";

  const dot = document.createElement("span");
  const label = document.createElement("span");

  wrapper.appendChild(dot);
  wrapper.appendChild(label);

  function applyState(isActive: boolean): void {
    if (isActive) {
      dot.textContent = "●";
      dot.className = "ai-heartbeat-dot";
      dot.style.color = "var(--ai-color-info)";
      label.textContent = "indexing…";
      label.style.color = "var(--ai-color-text-muted)";
    } else {
      dot.textContent = "●";
      dot.className = "";
      dot.style.color = "var(--ai-color-text-muted)";
      label.textContent = "idle";
      label.style.color = "var(--ai-color-text-muted)";
    }
  }

  applyState(active);

  wrapper.setActive = (isActive: boolean): void => {
    applyState(isActive);
  };

  return wrapper;
}
