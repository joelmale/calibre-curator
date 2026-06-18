import type { IAiApiClient, ISequenceGenerateResponse, ISequenceStep } from "../../types/api";
import { createAiSpinner } from "../atoms/AiSpinner";
import { createAiAlert } from "../atoms/AiAlert";
import { errorMessage } from "../../utils/result";
import { escapeHtml, sanitizeUrl } from "../../utils/dom";

export function createAiSequencePanel(client: IAiApiClient): HTMLElement {
  const panel = document.createElement("div");
  panel.className = "ai-sequence-panel";

  const form = document.createElement("form");
  const textarea = document.createElement("textarea");
  textarea.className = "form-control";
  textarea.rows = 2;
  textarea.placeholder =
    "Describe a reading goal… e.g. “understand the history of the Roman Republic from the ground up”";
  textarea.setAttribute("aria-label", "Reading goal");

  const btn = document.createElement("button");
  btn.type = "submit";
  btn.className = "btn btn-primary";
  btn.textContent = "Build sequence";
  btn.style.marginTop = "8px";

  form.appendChild(textarea);
  form.appendChild(btn);

  const output = document.createElement("div");
  output.style.marginTop = "16px";

  let current: ISequenceGenerateResponse | null = null;

  function renderSteps(data: ISequenceGenerateResponse): void {
    output.innerHTML = "";

    if (data.explanation) {
      const card = document.createElement("div");
      card.className = "panel panel-info";
      card.innerHTML = `<div class="panel-body"><strong>The arc:</strong> ${escapeHtml(data.explanation)}</div>`;
      output.appendChild(card);
    }

    if (data.steps.length === 0) {
      output.appendChild(createAiAlert("The model didn't return a usable sequence. Try a clearer goal.", "warning"));
      return;
    }

    const list = document.createElement("ol");
    list.className = "ai-sequence-list";
    for (const step of data.steps) {
      list.appendChild(renderStep(step));
    }
    output.appendChild(list);

    // Save controls
    const saveRow = document.createElement("div");
    saveRow.style.marginTop = "12px";
    const titleInput = document.createElement("input");
    titleInput.type = "text";
    titleInput.className = "form-control";
    titleInput.placeholder = "Name this sequence to save it as a collection";
    titleInput.style.maxWidth = "360px";
    titleInput.style.display = "inline-block";

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "btn btn-success";
    saveBtn.textContent = "Save as Collection";
    saveBtn.style.marginLeft = "8px";

    const status = document.createElement("span");
    status.className = "text-muted";
    status.style.marginLeft = "8px";

    saveBtn.addEventListener("click", () => {
      const title = titleInput.value.trim();
      if (!title || !current) {
        status.textContent = "Enter a name first.";
        return;
      }
      status.textContent = "Saving…";
      void client
        .saveSequence({ title, goal: current.goal, steps: current.steps })
        .then((res) => {
          status.textContent = res.ok
            ? `Saved (${res.data.itemCount} books).`
            : `Error: ${errorMessage(res.error)}`;
        });
    });

    saveRow.appendChild(titleInput);
    saveRow.appendChild(saveBtn);
    saveRow.appendChild(status);
    output.appendChild(saveRow);
  }

  function renderStep(step: ISequenceStep): HTMLElement {
    const li = document.createElement("li");
    li.className = "ai-sequence-step";
    li.style.marginBottom = "10px";
    const url = sanitizeUrl(`/book/${step.bookId}`);
    const authors = step.authors.map(escapeHtml).join(", ");
    li.innerHTML =
      `<a href="${url}" target="_blank"><strong>${escapeHtml(step.title)}</strong></a>` +
      (authors ? ` <small class="text-muted">${authors}</small>` : "") +
      (step.reason ? `<br><span>${escapeHtml(step.reason)}</span>` : "");
    return li;
  }

  async function run(goal: string): Promise<void> {
    output.innerHTML = "";
    output.appendChild(createAiSpinner("Selecting candidates and ordering the sequence…"));
    btn.disabled = true;

    const res = await client.generateSequence({ goal });
    btn.disabled = false;

    if (!res.ok) {
      output.innerHTML = "";
      output.appendChild(createAiAlert(errorMessage(res.error), "danger"));
      return;
    }
    current = res.data;
    renderSteps(res.data);
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const goal = textarea.value.trim();
    if (goal) void run(goal);
  });

  panel.appendChild(form);
  panel.appendChild(output);
  return panel;
}
