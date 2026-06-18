import type { IEmbeddingStatus } from "../../types/status";
import { createAiStatusTable } from "../molecules/AiStatusTable";

export function createAiEmbeddingInfo(embedding: IEmbeddingStatus): HTMLElement {
  const providerEl = document.createElement("code");
  providerEl.textContent = embedding.provider;

  const modelEl = document.createElement("code");
  modelEl.textContent = embedding.model;

  return createAiStatusTable([
    ["Provider", providerEl],
    ["Model",    modelEl],
  ]);
}
