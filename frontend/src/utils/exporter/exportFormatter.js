/**
 * Text formatting, escaping, and SVG chart generator for standalone HTML exporter.
 */

export function escapeHtml(text) {
  if (text === null || text === undefined) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export const EVIDENCE_TAG_STYLES = {
  "[evidence]": { bg: "rgba(16, 185, 129, 0.15)", text: "#10b981", border: "rgba(16, 185, 129, 0.3)" },
  "[derived metric]": { bg: "rgba(59, 130, 246, 0.15)", text: "#60a5fa", border: "rgba(59, 130, 246, 0.3)" },
  "[interpretation]": { bg: "rgba(139, 92, 246, 0.15)", text: "#a78bfa", border: "rgba(139, 92, 246, 0.3)" },
  "[hypothesis]": { bg: "rgba(245, 158, 11, 0.15)", text: "#fbbf24", border: "rgba(245, 158, 11, 0.3)" },
  "[data limitation]": { bg: "rgba(239, 68, 68, 0.15)", text: "#f87171", border: "rgba(239, 68, 68, 0.3)" },
  "[open question]": { bg: "rgba(236, 72, 153, 0.15)", text: "#f472b6", border: "rgba(236, 72, 153, 0.3)" },
  "[recommendation]": { bg: "rgba(20, 184, 166, 0.15)", text: "#2dd4bf", border: "rgba(20, 184, 166, 0.3)" },
};

export function parseFormattedText(text, brandColor) {
  if (!text) return "";
  const parts = String(text).split(/(\*\*[^*]+\*\*|\[(?:Evidence|Derived Metric|Interpretation|Hypothesis|Data Limitation|Open Question|Recommendation)\])/gi);
  return parts.map(part => {
    if (!part) return "";
    if (part.startsWith("**") && part.endsWith("**")) {
      return `<strong style="color: ${brandColor}; font-weight: 700;">${escapeHtml(part.slice(2, -2))}</strong>`;
    }
    const lower = part.toLowerCase();
    const tagStyle = EVIDENCE_TAG_STYLES[lower];
    if (tagStyle) {
      return `<span style="display:inline-flex;align-items:center;padding:1px 8px;margin-right:6px;border-radius:9999px;font-size:11px;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;background:${tagStyle.bg};color:${tagStyle.text};border:1px solid ${tagStyle.border};">${escapeHtml(part)}</span>`;
    }
    return escapeHtml(part);
  }).join("");
}

export function generateSvgChartHtml(chart, palette, brandColor) {
  if (!chart || !chart.categories || chart.categories.length === 0) {
    return `<div style="display:flex;align-items:center;justify-content:center;height:240px;color:rgba(255,255,255,0.4);border:1px dashed rgba(255,255,255,0.1);border-radius:8px;">No chart data</div>`;
  }

  const chartType = (chart.type || chart.chart_type || "column").toLowerCase();
  const categories = chart.categories || [];
  const seriesList = chart.series && chart.series.length > 0
    ? chart.series
    : [{ name: "Value", values: categories.map(() => 0) }];
  const unit = chart.unit || "";

  const fmtNum = (val) => {
    if (typeof val !== "number" || isNaN(val)) return "0";
    if (unit === "$") {
      if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`;
      if (val >= 1000) return `$${(val / 1000).toFixed(1)}k`;
      return `$${val.toFixed(0)}`;
    }
    if (unit === "%") return `${val.toFixed(1)}%`;
    if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `${(val / 1000).toFixed(1)}k`;
    return val % 1 === 0 ? val.toString() : val.toFixed(1);
  };

  // DONUT / PIE
  if (chartType === "donut" || chartType === "pie") {
    const isPie = chartType === "pie";
    const primarySeries = seriesList[0] || { values: [] };
    const values = (primarySeries.values || []).map(v => Math.max(0, Number(v) || 0));
    const total = values.reduce((a, b) => a + b, 0) || 1;

    let accumulatedAngle = 0;
    let pathsOrCircles = "";

    values.forEach((val, idx) => {
      const angle = (val / total) * 360;
      const startAngle = accumulatedAngle;
      accumulatedAngle += angle;
      const color = palette[idx % palette.length];

      if (isPie) {
        if (angle >= 359.9) {
          pathsOrCircles += `<circle cx="50" cy="50" r="42" fill="${color}" />`;
        } else {
          const startRad = ((startAngle - 90) * Math.PI) / 180;
          const endRad = ((startAngle + angle - 90) * Math.PI) / 180;
          const x1 = (50 + 42 * Math.cos(startRad)).toFixed(2);
          const y1 = (50 + 42 * Math.sin(startRad)).toFixed(2);
          const x2 = (50 + 42 * Math.cos(endRad)).toFixed(2);
          const y2 = (50 + 42 * Math.sin(endRad)).toFixed(2);
          const largeArc = angle > 180 ? 1 : 0;
          pathsOrCircles += `<path d="M 50,50 L ${x1},${y1} A 42,42 0 ${largeArc},1 ${x2},${y2} Z" fill="${color}" stroke="rgba(0,0,0,0.4)" stroke-width="1" />`;
        }
      } else {
        const r = 35;
        const c = 2 * Math.PI * r;
        const dashArray = `${((angle / 360) * c).toFixed(2)} ${c.toFixed(2)}`;
        const dashOffset = (-((startAngle / 360) * c)).toFixed(2);
        pathsOrCircles += `<circle cx="50" cy="50" r="${r}" fill="none" stroke="${color}" stroke-width="18" stroke-dasharray="${dashArray}" stroke-dashoffset="${dashOffset}" transform="rotate(-90 50 50)" />`;
      }
    });

    const legendItems = categories.map((cat, idx) => {
      const val = values[idx] || 0;
      const pct = Math.round((val / total) * 100);
      const col = palette[idx % palette.length];
      return `
        <div style="display:flex;align-items:center;gap:8px;font-size:12px;margin-bottom:6px;">
          <span style="width:10px;height:10px;border-radius:2px;background:${col};display:inline-block;"></span>
          <span style="color:#cbd5e1;flex:1;">${escapeHtml(cat)}</span>
          <span style="font-weight:600;color:#fff;">${pct}%</span>
        </div>
      `;
    }).join("");

    return `
      <div style="display:flex;align-items:center;gap:24px;width:100%;height:100%;">
        <div style="position:relative;width:190px;height:190px;flex-shrink:0;">
          <svg viewBox="0 0 100 100" style="width:100%;height:100%;">
            ${!isPie ? `<circle cx="50" cy="50" r="35" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="18" />` : ""}
            ${pathsOrCircles}
          </svg>
          ${!isPie ? `
            <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;">
              <span style="font-size:17px;font-weight:800;color:#fff;">${total >= 1000 ? (total/1000).toFixed(1)+'k' : total}</span>
              <span style="font-size:10px;color:#94a3b8;text-transform:uppercase;">${escapeHtml(unit || "Total")}</span>
            </div>
          ` : ""}
        </div>
        <div style="flex:1;max-height:220px;overflow-y:auto;">${legendItems}</div>
      </div>
    `;
  }

  // COLUMN / BAR
  const primarySeries = seriesList[0] || { values: [] };
  const values = (primarySeries.values || []).map(v => Number(v) || 0);
  const maxVal = Math.max(...values, 1);

  const bars = categories.map((cat, idx) => {
    const val = values[idx] || 0;
    const heightPct = Math.max(4, Math.round((val / maxVal) * 100));
    const col = palette[idx % palette.length];
    return `
      <div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:8px;height:100%;justify-content:flex-end;">
        <span style="font-size:11px;font-weight:600;color:#cbd5e1;">${fmtNum(val)}</span>
        <div style="width:100%;max-width:48px;height:${heightPct}%;background:${col};border-radius:4px 4px 0 0;box-shadow:0 2px 8px rgba(0,0,0,0.3);"></div>
        <span style="font-size:11px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:70px;text-align:center;" title="${escapeHtml(cat)}">${escapeHtml(cat)}</span>
      </div>
    `;
  }).join("");

  return `
    <div style="display:flex;align-items:flex-end;gap:12px;width:100%;height:220px;padding-top:20px;border-bottom:1px solid rgba(255,255,255,0.1);">
      ${bars}
    </div>
  `;
}
