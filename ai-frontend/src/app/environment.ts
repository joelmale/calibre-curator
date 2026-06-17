const root = document.getElementById("ai-curation-root");
const rawBase = root?.dataset["apiBase"] ?? "/ai/api/";

// Strip trailing slash so paths like "/status" join cleanly as baseUrl + "/status"
export const API_BASE: string = rawBase.endsWith("/")
  ? rawBase.slice(0, -1)
  : rawBase;
