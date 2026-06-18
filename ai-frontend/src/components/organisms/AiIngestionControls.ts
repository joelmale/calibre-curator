import type { IAiApiClient } from "../../types/api";
import { createAiButton } from "../atoms/AiButton";
import { createAiAlert } from "../atoms/AiAlert";
import { errorMessage } from "../../utils/result";

export function createAiIngestionControls(
  client: IAiApiClient,
  onTriggered?: () => void,
): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.className = "ai-ingestion-controls";
  wrapper.style.padding = "8px";

  const feedback = document.createElement("div");
  feedback.style.marginTop = "8px";

  const btn = createAiButton("Scan Library Now", async () => {
    btn.disabled = true;
    btn.textContent = "Queuing scan…";
    feedback.innerHTML = "";

    const res = await client.triggerIngestion();
    btn.disabled = false;
    btn.textContent = "Scan Library Now";

    if (!res.ok) {
      const msg = res.error.error === "already_running"
        ? "A scan is already in progress."
        : errorMessage(res.error);
      feedback.appendChild(createAiAlert(msg, "warning"));
    } else {
      feedback.appendChild(
        createAiAlert(`Scan queued (run #${res.data.runId}) — status will update automatically.`, "success"),
      );
      onTriggered?.();
    }
  });

  wrapper.appendChild(btn);
  wrapper.appendChild(feedback);
  return wrapper;
}
