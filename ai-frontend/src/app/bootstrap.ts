import { API_BASE } from "./environment";
import { HttpClient } from "../api/httpClient";
import { AiApiClient } from "../api/aiClient";
import { AiDashboardPage } from "../components/pages/AiDashboardPage";

const http = new HttpClient(API_BASE);
const client = new AiApiClient(http);

const root = document.getElementById("ai-curation-root");
if (root instanceof HTMLElement) {
  const page = new AiDashboardPage(root, client);
  page.mount();
}
