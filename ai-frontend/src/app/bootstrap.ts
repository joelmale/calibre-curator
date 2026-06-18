import { API_BASE } from "./environment";
import { HttpClient } from "../api/httpClient";
import { AiApiClient } from "../api/aiClient";
import { AiDashboardPage } from "../components/pages/AiDashboardPage";
import { AiMoodPage } from "../components/pages/AiMoodPage";
import { AiSequencePage } from "../components/pages/AiSequencePage";

const http = new HttpClient(API_BASE);
const client = new AiApiClient(http);

const root = document.getElementById("ai-curation-root");

interface IRoute {
  readonly hash: string;
  readonly label: string;
  mount(container: HTMLElement): void;
}

const routes: readonly IRoute[] = [
  {
    hash: "",
    label: "Discover",
    mount: (c) => new AiDashboardPage(c, client).mount(),
  },
  {
    hash: "#mood",
    label: "Mood Wizard",
    mount: (c) => new AiMoodPage(c, client).mount(),
  },
  {
    hash: "#sequences",
    label: "Sequence Builder",
    mount: (c) => new AiSequencePage(c, client).mount(),
  },
];

function buildNav(active: string): HTMLElement {
  const nav = document.createElement("ul");
  nav.className = "nav nav-pills ai-spa-nav";
  nav.style.marginBottom = "20px";
  for (const route of routes) {
    const li = document.createElement("li");
    li.setAttribute("role", "presentation");
    if (route.hash === active) li.className = "active";
    const a = document.createElement("a");
    a.href = route.hash || "#";
    a.textContent = route.label;
    li.appendChild(a);
    nav.appendChild(li);
  }
  return nav;
}

function render(container: HTMLElement): void {
  const active = window.location.hash;
  const route = routes.find((r) => r.hash === active) ?? routes[0]!;

  container.innerHTML = "";
  container.appendChild(buildNav(route.hash));

  const pageHolder = document.createElement("div");
  container.appendChild(pageHolder);
  route.mount(pageHolder);
}

if (root instanceof HTMLElement) {
  window.addEventListener("hashchange", () => render(root));
  render(root);
}
