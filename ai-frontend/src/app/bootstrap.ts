import { API_BASE } from "./environment";
import { initTheme } from "./theme";
import { HttpClient } from "../api/httpClient";
import { AiApiClient } from "../api/aiClient";
import { AiDashboardPage } from "../components/pages/AiDashboardPage";
import { AiMoodPage } from "../components/pages/AiMoodPage";
import { AiSequencePage } from "../components/pages/AiSequencePage";

// Apply theme tokens before any rendering to avoid flash-of-wrong-theme.
initTheme();

const http = new HttpClient(API_BASE);
const client = new AiApiClient(http);

const root = document.getElementById("ai-curation-root");

interface IRoute {
  readonly hash: string;
  mount(container: HTMLElement): void;
}

// Hash routes for the SPA. Navigation between them is driven by the shared
// server-rendered tab bar (_ai_nav.html); this just maps the URL hash to a page.
const routes: readonly IRoute[] = [
  { hash: "", mount: (c) => new AiDashboardPage(c, client).mount() },
  { hash: "#mood", mount: (c) => new AiMoodPage(c, client).mount() },
  { hash: "#sequences", mount: (c) => new AiSequencePage(c, client).mount() },
];

function render(container: HTMLElement): void {
  const active = window.location.hash;
  const route = routes.find((r) => r.hash === active) ?? routes[0]!;
  container.innerHTML = "";
  route.mount(container);
}

if (root instanceof HTMLElement) {
  window.addEventListener("hashchange", () => render(root));
  render(root);
}
