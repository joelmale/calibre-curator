/**
 * AiDonutChart — dependency-free inline SVG donut chart.
 *
 * Renders a donut with slices for each status segment, plus a horizontal
 * bar-style legend showing label + count.  Uses --ai-color-* tokens so it
 * reads correctly on both the light default and the caliBlur dark theme.
 */

/** Maps ingestion_status → CSS token color (var(...)) */
const STATUS_COLORS: Record<string, string> = {
  indexed:    "var(--ai-color-success)",
  pending:    "var(--ai-color-primary)",
  chunked:    "var(--ai-color-info)",
  extracting: "var(--ai-color-warning)",
  failed:     "var(--ai-color-danger)",
};

const STATUS_ORDER = ["indexed", "pending", "chunked", "extracting", "failed"];

function fallbackColor(index: number): string {
  const FALLBACKS = [
    "var(--ai-color-primary)",
    "var(--ai-color-info)",
    "var(--ai-color-warning)",
    "var(--ai-color-danger)",
    "var(--ai-color-text-muted)",
  ];
  return FALLBACKS[index % FALLBACKS.length] ?? "var(--ai-color-text-muted)";
}

function colorFor(status: string, index: number): string {
  return STATUS_COLORS[status] ?? fallbackColor(index);
}

/** Build a single SVG <path> arc segment. */
function arcPath(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number,
  color: string,
  holeRadius: number,
): SVGPathElement {
  // Convert angles to radians, starting at -π/2 (12 o'clock)
  const s = (startAngle - 90) * (Math.PI / 180);
  const e = (endAngle - 90) * (Math.PI / 180);

  const x1 = cx + r * Math.cos(s);
  const y1 = cy + r * Math.sin(s);
  const x2 = cx + r * Math.cos(e);
  const y2 = cy + r * Math.sin(e);

  const ix1 = cx + holeRadius * Math.cos(e);
  const iy1 = cy + holeRadius * Math.sin(e);
  const ix2 = cx + holeRadius * Math.cos(s);
  const iy2 = cy + holeRadius * Math.sin(s);

  const largeArc = endAngle - startAngle > 180 ? 1 : 0;

  const d = [
    `M ${x1} ${y1}`,
    `A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`,
    `L ${ix1} ${iy1}`,
    `A ${holeRadius} ${holeRadius} 0 ${largeArc} 0 ${ix2} ${iy2}`,
    "Z",
  ].join(" ");

  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", d);
  path.setAttribute("fill", color);
  return path;
}

export interface DonutSlice {
  label: string;
  count: number;
}

export function createAiDonutChart(slices: DonutSlice[]): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.className = "ai-donut-chart";
  wrapper.style.cssText = "display:flex;align-items:center;gap:16px;flex-wrap:wrap;";

  const total = slices.reduce((s, d) => s + d.count, 0);

  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  const SIZE = 120;
  const R = 50;
  const HOLE = 28;
  const CX = SIZE / 2;
  const CY = SIZE / 2;

  svg.setAttribute("viewBox", `0 0 ${SIZE} ${SIZE}`);
  svg.setAttribute("width", String(SIZE));
  svg.setAttribute("height", String(SIZE));
  svg.setAttribute("aria-label", "Indexing status distribution");
  svg.style.flexShrink = "0";

  if (total === 0) {
    // Empty state: grey ring
    const circle = document.createElementNS(svgNS, "circle");
    circle.setAttribute("cx", String(CX));
    circle.setAttribute("cy", String(CY));
    circle.setAttribute("r", String((R + HOLE) / 2));
    circle.setAttribute("fill", "none");
    circle.setAttribute("stroke", "var(--ai-color-border)");
    circle.setAttribute("stroke-width", String(R - HOLE));
    svg.appendChild(circle);
  } else {
    // Check if a single slice is ~100% (would cause degenerate arc where start==end)
    const nonZeroSlices = slices.filter(s => s.count > 0);
    if (nonZeroSlices.length === 1) {
      // Render a full circle ring for the sole slice instead of a degenerate arc
      const sole = nonZeroSlices[0]!;
      const ring = document.createElementNS(svgNS, "circle");
      ring.setAttribute("cx", String(CX));
      ring.setAttribute("cy", String(CY));
      ring.setAttribute("r", String((R + HOLE) / 2));
      ring.setAttribute("fill", "none");
      ring.setAttribute("stroke", colorFor(sole.label, slices.indexOf(sole)));
      ring.setAttribute("stroke-width", String(R - HOLE));
      svg.appendChild(ring);
    } else {
      let startAngle = 0;
      slices.forEach((slice, i) => {
        if (slice.count === 0) return;
        // Cap sweep at 359.99° to avoid degenerate arcs when one slice dominates
        const sweep = Math.min((slice.count / total) * 360, 359.99);
        const endAngle = startAngle + sweep;
        const path = arcPath(CX, CY, R, startAngle, endAngle, colorFor(slice.label, i), HOLE);
        svg.appendChild(path);
        startAngle = endAngle;
      });
    }
  }

  // Center label: percentage indexed
  const indexedSlice = slices.find(s => s.label === "indexed");
  const indexedPct = total > 0 && indexedSlice
    ? Math.round((indexedSlice.count / total) * 100)
    : 0;

  const centerText = document.createElementNS(svgNS, "text");
  centerText.setAttribute("x", String(CX));
  centerText.setAttribute("y", String(CY - 4));
  centerText.setAttribute("text-anchor", "middle");
  centerText.setAttribute("dominant-baseline", "middle");
  centerText.setAttribute("font-size", "16");
  centerText.setAttribute("font-weight", "bold");
  centerText.setAttribute("fill", "var(--ai-color-text)");
  centerText.textContent = `${indexedPct}%`;
  svg.appendChild(centerText);

  const subText = document.createElementNS(svgNS, "text");
  subText.setAttribute("x", String(CX));
  subText.setAttribute("y", String(CY + 12));
  subText.setAttribute("text-anchor", "middle");
  subText.setAttribute("font-size", "9");
  subText.setAttribute("fill", "var(--ai-color-text-muted)");
  subText.textContent = "indexed";
  svg.appendChild(subText);

  wrapper.appendChild(svg);

  // Legend
  const legend = document.createElement("div");
  legend.style.cssText = "display:flex;flex-direction:column;gap:5px;min-width:0;";

  slices.forEach((slice, i) => {
    if (slice.count === 0) return;
    const row = document.createElement("div");
    row.style.cssText = "display:flex;align-items:center;gap:6px;font-size:12px;";

    const swatch = document.createElement("span");
    swatch.style.cssText = `
      display:inline-block;width:10px;height:10px;border-radius:2px;
      background:${colorFor(slice.label, i)};flex-shrink:0;
    `;

    const label = document.createElement("span");
    label.style.color = "var(--ai-color-text-muted)";
    label.textContent = slice.label;

    const count = document.createElement("span");
    count.style.cssText = "margin-left:auto;font-weight:600;color:var(--ai-color-text);white-space:nowrap;";
    count.textContent = slice.count.toLocaleString();

    row.appendChild(swatch);
    row.appendChild(label);
    row.appendChild(count);
    legend.appendChild(row);
  });

  wrapper.appendChild(legend);
  return wrapper;
}

/** createAiStatusBarChart — horizontal bar chart showing per-status counts. */
export function createAiStatusBarChart(breakdown: Readonly<Record<string, number>>): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.className = "ai-status-bar-chart";
  wrapper.style.cssText = "display:flex;flex-direction:column;gap:6px;";

  const total = Object.values(breakdown).reduce((s, n) => s + n, 0);
  if (total === 0) {
    const empty = document.createElement("p");
    empty.className = "text-muted";
    empty.style.margin = "0";
    empty.style.fontSize = "12px";
    empty.textContent = "No data";
    wrapper.appendChild(empty);
    return wrapper;
  }

  // Merge STATUS_ORDER + any unexpected keys
  const keys = [
    ...STATUS_ORDER.filter(k => breakdown[k] !== undefined),
    ...Object.keys(breakdown).filter(k => !STATUS_ORDER.includes(k)),
  ];

  keys.forEach((key, i) => {
    const count = breakdown[key] ?? 0;
    const pct = (count / total) * 100;

    const row = document.createElement("div");
    row.style.cssText = "display:flex;align-items:center;gap:8px;font-size:12px;";

    const keyLabel = document.createElement("span");
    keyLabel.style.cssText = "width:72px;flex-shrink:0;color:var(--ai-color-text-muted);text-align:right;";
    keyLabel.textContent = key;

    const barWrap = document.createElement("div");
    barWrap.style.cssText = `
      flex:1;height:10px;background:var(--ai-color-surface-alt);
      border-radius:4px;overflow:hidden;border:1px solid var(--ai-color-border);
    `;

    const bar = document.createElement("div");
    bar.style.cssText = `
      height:100%;width:${pct.toFixed(1)}%;
      background:${colorFor(key, i)};
      border-radius:4px;transition:width 0.3s ease;
    `;
    barWrap.appendChild(bar);

    const countLabel = document.createElement("span");
    countLabel.style.cssText = "width:52px;flex-shrink:0;font-weight:600;color:var(--ai-color-text);";
    countLabel.textContent = count.toLocaleString();

    row.appendChild(keyLabel);
    row.appendChild(barWrap);
    row.appendChild(countLabel);
    wrapper.appendChild(row);
  });

  return wrapper;
}

/** Build ordered slice array from the statusBreakdown map. */
export function breakdownToSlices(breakdown: Readonly<Record<string, number>>): DonutSlice[] {
  const seen = new Set<string>();
  const slices: DonutSlice[] = [];

  for (const key of STATUS_ORDER) {
    if (breakdown[key] !== undefined) {
      slices.push({ label: key, count: breakdown[key]! });
      seen.add(key);
    }
  }
  // Append any unexpected statuses
  for (const [key, count] of Object.entries(breakdown)) {
    if (!seen.has(key)) {
      slices.push({ label: key, count });
    }
  }
  return slices;
}
