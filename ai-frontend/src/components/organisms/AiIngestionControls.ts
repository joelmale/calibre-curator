import type { IAiApiClient } from "../../types/api";
import { createAiButton } from "../atoms/AiButton";
import { createAiAlert } from "../atoms/AiAlert";
import { errorMessage } from "../../utils/result";

const LIMIT_OPTIONS: ReadonlyArray<{ label: string; value: number | null }> = [
  { label: "All new / changed books", value: null },
  { label: "Next 10 books",           value: 10   },
  { label: "Next 25 books",           value: 25   },
  { label: "Next 50 books",           value: 50   },
  { label: "Next 100 books",          value: 100  },
  { label: "Next 250 books",          value: 250  },
];

export function createAiIngestionControls(
  client: IAiApiClient,
  onTriggered?: () => void,
): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.className = "ai-ingestion-controls";
  wrapper.style.cssText = "padding:8px;display:flex;align-items:center;gap:8px;flex-wrap:wrap";

  // Limit selector
  const select = document.createElement("select");
  select.className = "form-control input-sm";
  select.style.cssText = "width:auto;display:inline-block";
  select.setAttribute("aria-label", "Scan limit");
  LIMIT_OPTIONS.forEach(({ label, value }) => {
    const opt = document.createElement("option");
    opt.value = value == null ? "" : String(value);
    opt.textContent = label;
    select.appendChild(opt);
  });

  const feedback = document.createElement("div");
  feedback.style.cssText = "margin-top:8px;width:100%";

  const btn = createAiButton("Scan Library Now", async () => {
    const rawVal = select.value;
    const limit = rawVal === "" ? null : parseInt(rawVal, 10);

    btn.disabled = true;
    btn.textContent = "Queuing scan…";
    feedback.innerHTML = "";

    const res = await client.triggerIngestion(limit);
    btn.disabled = false;
    btn.textContent = "Scan Library Now";

    if (!res.ok) {
      const msg = res.error.error === "already_running"
        ? "A scan is already in progress."
        : errorMessage(res.error);
      feedback.appendChild(createAiAlert(msg, "warning"));
    } else {
      const limitNote = res.data.limit != null
        ? ` (limited to ${res.data.limit} books)`
        : "";
      feedback.appendChild(
        createAiAlert(
          `Scan queued (run #${res.data.runId})${limitNote} — status will refresh shortly.`,
          "success",
        ),
      );
      onTriggered?.();
    }
  });

  wrapper.appendChild(select);
  wrapper.appendChild(btn);
  wrapper.appendChild(feedback);
  return wrapper;
}
