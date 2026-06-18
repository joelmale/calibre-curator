import type { IAiApiClient } from "../../types/api";
import { createAiButton } from "../atoms/AiButton";
import { createAiAlert } from "../atoms/AiAlert";
import { errorMessage } from "../../utils/result";

export function createAiIngestionControls(client: IAiApiClient): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.className = "ai-ingestion-controls";

  const feedback = document.createElement("div");
  feedback.style.marginTop = "8px";

  const btn = createAiButton("Scan Library Now", async () => {
    btn.disabled = true;
    btn.textContent = "Scanning…";
    feedback.innerHTML = "";

    const res = await client.getStatus();
    btn.disabled = false;
    btn.textContent = "Scan Library Now";

    if (!res.ok) {
      feedback.appendChild(createAiAlert(errorMessage(res.error), "danger"));
    } else {
      feedback.appendChild(createAiAlert("Scan triggered — refresh status in a moment.", "success"));
    }
  });

  wrapper.appendChild(btn);
  wrapper.appendChild(feedback);
  return wrapper;
}
