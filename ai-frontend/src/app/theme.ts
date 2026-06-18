/**
 * Theme detection for the AI Curator.
 *
 * CWA's theme signal:
 *   - Server: `g.current_theme == 1` → caliBlur dark theme
 *     Templates emit `data-ai-theme="dark"` on the root elements when dark.
 *   - DOM:  `document.body.classList.contains('blur')` — CWA adds the class
 *     "blur" to <body> whenever caliBlur (dark) is active.
 *
 * Luminance fallback:
 *   If neither signal is found, we sample the computed background-color of
 *   <body> and calculate relative luminance; if luminance < 0.18 the host is
 *   considered dark.  This covers future unknown CWA themes without requiring
 *   code changes.
 *
 * The result is written as `data-ai-theme="dark"|"light"` on:
 *   - #ai-curation-root   (the SPA mount point)
 *   - #ai-nav-root        (the server-rendered nav bar)
 *
 * A MutationObserver re-evaluates whenever the body class list changes so that
 * the curator follows CWA live if the user switches theme without a full page
 * reload (CWA's theme picker uses a soft swap).
 */

type AiTheme = "dark" | "light";

/** Compute relative luminance from an rgb(r, g, b) / rgba(r, g, b, a) string. */
function luminanceFromRgbString(rgb: string): number | null {
  const match = /rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)/.exec(rgb);
  if (!match) return null;
  const toLinear = (c: number): number => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const r = toLinear(parseInt(match[1]!, 10));
  const g = toLinear(parseInt(match[2]!, 10));
  const b = toLinear(parseInt(match[3]!, 10));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function detectTheme(): AiTheme {
  // 1) Server-side signal: body class "blur" → CWA caliBlur (dark)
  if (document.body.classList.contains("blur")) {
    return "dark";
  }

  // 2) Explicit data-ai-theme already set (e.g. by server template)
  //    If the root is already annotated trust it — avoids double-work.
  const root = document.getElementById("ai-curation-root");
  const existing = root?.dataset["aiTheme"];
  if (existing === "dark" || existing === "light") {
    return existing;
  }

  // 3) Luminance fallback — sample <body> background
  const bodyBg = window.getComputedStyle(document.body).backgroundColor;
  const lum = luminanceFromRgbString(bodyBg);
  if (lum !== null && lum < 0.18) {
    return "dark";
  }

  return "light";
}

function applyTheme(theme: AiTheme): void {
  const targets = [
    document.getElementById("ai-curation-root"),
    document.getElementById("ai-nav-root"),
  ];
  for (const el of targets) {
    if (el) {
      el.dataset["aiTheme"] = theme;
    }
  }
}

/** Initialise theme detection and set up a live observer. */
export function initTheme(): void {
  applyTheme(detectTheme());

  // Re-evaluate if CWA's body class changes (live theme switch).
  const observer = new MutationObserver(() => {
    applyTheme(detectTheme());
  });
  observer.observe(document.body, { attributes: true, attributeFilter: ["class"] });
}
