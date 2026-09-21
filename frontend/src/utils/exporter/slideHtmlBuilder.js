/**
 * Slide HTML layout generators for standalone presentation export.
 */

import { escapeHtml, parseFormattedText, generateSvgChartHtml } from "./exportFormatter";

export function buildSlideHtml(slide, index, total, theme) {
  const layout = slide.layout || "chart_narrative";
  const brandColor = theme.accent_color || "#ff8a62";
  const cardBg = theme.card_bg || "#1e293b";
  const cardBorder = theme.card_border || "rgba(255,255,255,0.08)";
  const palette = theme.chart_palette || ["#ff8a62", "#7ee7d9", "#8ef0c8", "#a78bfa", "#fbbf24"];

  const headerHtml = `
    <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:28px;">
      <div>
        <div style="font-size:12px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:${brandColor};margin-bottom:8px;">
          ${escapeHtml(slide.category || "EXECUTIVE REVIEW")}
        </div>
        <h2 style="font-family:var(--font-display);font-size:38px;font-weight:800;color:#ffffff;line-height:1.2;margin:0 0 6px 0;">
          ${escapeHtml(slide.title)}
        </h2>
        ${slide.subtitle ? `<div style="font-size:17px;color:#94a3b8;">${escapeHtml(slide.subtitle)}</div>` : ""}
      </div>
      ${slide.evidence_id ? `
        <div style="display:flex;align-items:center;gap:6px;padding:6px 14px;background:rgba(255,255,255,0.05);border:1px solid ${cardBorder};border-radius:9999px;font-size:12px;color:#94a3b8;">
          <span style="color:#10b981;">&#x2714;</span>
          <span>${escapeHtml(slide.evidence_id)}</span>
        </div>
      ` : ""}
    </div>
  `;

  const footerHtml = `
    <div style="position:absolute;bottom:36px;left:70px;right:70px;display:flex;align-items:center;justify-content:space-between;font-size:13px;color:#64748b;border-top:1px solid rgba(255,255,255,0.08);padding-top:16px;">
      <div style="display:flex;align-items:center;gap:8px;">
        <span style="color:#10b981;">&#x25CF;</span>
        <span>Evidence: ${escapeHtml((slide.evidence_sources || ["Verified Ground Truth Engine"]).join(" · "))}</span>
      </div>
      <div>
        Slide <strong style="color:${brandColor};">${index + 1}</strong> of ${total}
      </div>
    </div>
  `;

  let bodyHtml = "";

  // LAYOUT 1: TITLE HERO
  if (layout === "title_hero") {
    const bulletsHtml = (slide.bullets || []).map(b => `
      <li style="display:flex;align-items:flex-start;gap:12px;margin-bottom:12px;font-size:18px;color:#cbd5e1;">
        <span style="width:8px;height:8px;border-radius:50%;background:${brandColor};margin-top:7px;flex-shrink:0;"></span>
        <div>${parseFormattedText(b, brandColor)}</div>
      </li>
    `).join("");

    const metricsHtml = (slide.metrics || []).map(m => `
      <div style="background:${cardBg};border:1px solid ${cardBorder};border-radius:14px;padding:22px;display:flex;flex-direction:column;gap:6px;">
        <span style="font-size:13px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;">${escapeHtml(m.label)}</span>
        <span style="font-size:36px;font-weight:800;color:${brandColor};font-family:var(--font-display);">${escapeHtml(m.value)}</span>
        ${m.context ? `<span style="font-size:12px;color:#64748b;">${escapeHtml(m.context)}</span>` : ""}
      </div>
    `).join("");

    bodyHtml = `
      <div style="display:grid;grid-template-columns:1.2fr 0.8fr;gap:36px;align-items:start;">
        <div style="background:${cardBg};border:1px solid ${cardBorder};border-radius:18px;padding:36px;box-shadow:0 12px 32px rgba(0,0,0,0.4);">
          <div style="font-size:22px;line-height:1.6;color:#f8fafc;margin-bottom:24px;">
            ${parseFormattedText(slide.narrative, brandColor)}
          </div>
          <ul style="list-style:none;padding:0;margin:0;">${bulletsHtml}</ul>
        </div>
        <div style="display:flex;flex-direction:column;gap:18px;">
          ${metricsHtml}
        </div>
      </div>
    `;
  }

  // LAYOUT 2: KPI SUMMARY
  else if (layout === "kpi_summary") {
    const kpiCards = (slide.metrics || []).map(m => `
      <div style="background:${cardBg};border:1px solid ${cardBorder};border-radius:18px;padding:32px;display:flex;flex-direction:column;gap:10px;box-shadow:0 10px 30px rgba(0,0,0,0.3);">
        <span style="font-size:14px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;">${escapeHtml(m.label)}</span>
        <span style="font-size:48px;font-weight:900;color:${brandColor};font-family:var(--font-display);line-height:1;">${escapeHtml(m.value)}</span>
        ${m.change ? `<span style="font-size:14px;font-weight:700;color:#10b981;">&#x2191; ${escapeHtml(m.change)} vs prior</span>` : ""}
        ${m.benchmark ? `<span style="font-size:13px;color:#64748b;">Benchmark: ${escapeHtml(m.benchmark)}</span>` : ""}
        ${m.context ? `<span style="font-size:13px;color:#94a3b8;margin-top:6px;">${escapeHtml(m.context)}</span>` : ""}
      </div>
    `).join("");

    bodyHtml = `
      <div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(260px, 1fr));gap:24px;margin-bottom:28px;">
          ${kpiCards}
        </div>
        ${slide.narrative ? `
          <div style="background:rgba(255,255,255,0.03);border-left:4px solid ${brandColor};padding:18px 24px;border-radius:0 12px 12px 0;font-size:17px;color:#cbd5e1;line-height:1.6;">
            ${parseFormattedText(slide.narrative, brandColor)}
          </div>
        ` : ""}
      </div>
    `;
  }

  // LAYOUT 3: CHART NARRATIVE
  else if (layout === "chart_narrative") {
    const bulletsHtml = (slide.bullets || []).map(b => `
      <li style="display:flex;align-items:flex-start;gap:10px;margin-bottom:12px;font-size:16px;color:#cbd5e1;line-height:1.5;">
        <span style="width:6px;height:6px;border-radius:50%;background:${brandColor};margin-top:8px;flex-shrink:0;"></span>
        <div>${parseFormattedText(b, brandColor)}</div>
      </li>
    `).join("");

    bodyHtml = `
      <div style="display:grid;grid-template-columns:1.2fr 1fr;gap:36px;align-items:center;">
        <div style="background:${cardBg};border:1px solid ${cardBorder};border-radius:18px;padding:32px;box-shadow:0 12px 30px rgba(0,0,0,0.35);">
          ${generateSvgChartHtml(slide.chart, palette, brandColor)}
        </div>
        <div style="background:${cardBg};border:1px solid ${cardBorder};border-radius:18px;padding:32px;">
          <div style="font-size:19px;line-height:1.6;color:#ffffff;margin-bottom:20px;font-weight:500;">
            ${parseFormattedText(slide.narrative, brandColor)}
          </div>
          <ul style="list-style:none;padding:0;margin:0;">${bulletsHtml}</ul>
        </div>
      </div>
    `;
  }

  // LAYOUT 4: FULL CHART TAKEAWAY
  else if (layout === "full_chart_takeaway") {
    bodyHtml = `
      <div style="display:flex;flex-direction:column;gap:20px;">
        <div style="background:rgba(255,255,255,0.03);border-left:4px solid ${brandColor};padding:16px 24px;border-radius:0 10px 10px 0;font-size:18px;color:#ffffff;">
          ${parseFormattedText(slide.narrative, brandColor)}
        </div>
        <div style="background:${cardBg};border:1px solid ${cardBorder};border-radius:18px;padding:32px;height:380px;">
          ${generateSvgChartHtml(slide.chart, palette, brandColor)}
        </div>
      </div>
    `;
  }

  // LAYOUT 5: TWO CHARTS
  else if (layout === "two_charts") {
    const chart1 = slide.chart || {};
    const chart2 = slide.second_chart || {};
    bodyHtml = `
      <div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-bottom:20px;">
          <div style="background:${cardBg};border:1px solid ${cardBorder};border-radius:18px;padding:26px;">
            <div style="font-size:14px;font-weight:700;color:#94a3b8;margin-bottom:12px;">${escapeHtml(chart1.title || "Primary Analysis")}</div>
            ${generateSvgChartHtml(chart1, palette, brandColor)}
          </div>
          <div style="background:${cardBg};border:1px solid ${cardBorder};border-radius:18px;padding:26px;">
            <div style="font-size:14px;font-weight:700;color:#94a3b8;margin-bottom:12px;">${escapeHtml(chart2.title || "Comparative View")}</div>
            ${generateSvgChartHtml(chart2, palette.slice().reverse(), brandColor)}
          </div>
        </div>
        <div style="font-size:16px;color:#94a3b8;line-height:1.5;">${parseFormattedText(slide.narrative, brandColor)}</div>
      </div>
    `;
  }

  // LAYOUT 6: COMPARISON SPLIT
  else if (layout === "comparison_split") {
    const leftItems = (slide.left_points || slide.bullets?.slice(0, Math.ceil((slide.bullets.length||0)/2)) || []).map(p => `
      <li style="margin-bottom:10px;font-size:16px;color:#cbd5e1;">&#x2714; ${parseFormattedText(p, brandColor)}</li>
    `).join("");

    const rightItems = (slide.right_points || slide.bullets?.slice(Math.ceil((slide.bullets.length||0)/2)) || []).map(p => `
      <li style="margin-bottom:10px;font-size:16px;color:#cbd5e1;">&#x26A0; ${parseFormattedText(p, "#f59e0b")}</li>
    `).join("");

    bodyHtml = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:28px;">
        <div style="background:${cardBg};border:1px solid rgba(16,185,129,0.3);border-radius:18px;padding:32px;">
          <h3 style="color:#10b981;font-size:20px;font-weight:700;margin:0 0 16px 0;">${escapeHtml(slide.left_title || "Key Strengths & Gains")}</h3>
          <ul style="list-style:none;padding:0;margin:0;">${leftItems}</ul>
        </div>
        <div style="background:${cardBg};border:1px solid rgba(245,158,11,0.3);border-radius:18px;padding:32px;">
          <h3 style="color:#f59e0b;font-size:20px;font-weight:700;margin:0 0 16px 0;">${escapeHtml(slide.right_title || "Headwinds & Strategic Risks")}</h3>
          <ul style="list-style:none;padding:0;margin:0;">${rightItems}</ul>
        </div>
      </div>
    `;
  }

  // LAYOUT 7: ACTION PLAN
  else if (layout === "action_plan") {
    const rawActions = slide.initiatives || slide.structured_proposals || slide.actions || [];
    const actions = rawActions.slice(0, 3).map((act, i) => {
      const priority = String(act.priority || "HIGH").toUpperCase();
      const owner = act.owner || act.owner_role || "Unassigned - Operations Lead";
      const title = act.title || act.proposed_response || act.initiative || `Initiative ${i + 1}`;
      const finding = act.finding || act.motivating_finding || act.description || "";
      const metric = act.metric || act.success_metric || "";
      const dependency = act.dependency || act.dependencies || "";

      return `
      <div style="background:${cardBg};border:1px solid ${cardBorder};border-radius:14px;padding:22px;display:flex;flex-direction:column;gap:10px;box-shadow:0 8px 24px rgba(0,0,0,0.3);">
        <div style="display:flex;align-items:center;justify-content:space-between;">
          <span style="font-size:11px;font-weight:700;padding:2px 8px;border-radius:9999px;background:rgba(239,68,68,0.15);color:#f87171;border:1px solid rgba(239,68,68,0.3);text-transform:uppercase;">${escapeHtml(priority)}</span>
          <span style="font-size:12px;font-weight:600;color:${theme.accent_color || "#7ee7d9"};">${escapeHtml(owner)}</span>
        </div>
        <div style="font-size:16px;font-weight:800;color:#ffffff;line-height:1.3;">${escapeHtml(title)}</div>
        ${finding ? `
          <div style="font-size:13px;color:#94a3b8;line-height:1.4;">
            <strong style="color:${brandColor};">Finding:</strong> ${escapeHtml(finding)}
          </div>
        ` : ""}
        <div style="margin-top:auto;padding-top:10px;border-top:1px solid rgba(255,255,255,0.08);font-size:12px;color:#64748b;display:flex;flex-direction:column;gap:4px;">
          ${metric ? `<div><strong style="color:#cbd5e1;">Target:</strong> ${escapeHtml(metric)}</div>` : ""}
          ${dependency ? `<div><strong style="color:#cbd5e1;">Prerequisite:</strong> ${escapeHtml(dependency)}</div>` : ""}
        </div>
      </div>
    `;
    }).join("");

    bodyHtml = `
      <div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(260px, 1fr));gap:20px;margin-bottom:20px;">
          ${actions}
        </div>
        ${slide.narrative ? `
          <div style="background:rgba(255,255,255,0.03);border-left:4px solid ${brandColor};padding:14px 20px;border-radius:0 10px 10px 0;font-size:16px;color:#cbd5e1;line-height:1.5;">
            ${parseFormattedText(slide.narrative, brandColor)}
          </div>
        ` : ""}
      </div>
    `;
  }

  // DEFAULT / TABLE DETAIL
  else {
    const tableData = slide.table || {};
    const tableHeaders = tableData.headers || slide.table_headers || ["Metric", "Value", "Status", "Variance"];
    const tableRows = tableData.rows || slide.table_rows || [];
    const rows = tableRows.slice(0, 8).map(row => `
      <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
        ${(row || []).map((cell, cIdx) => `<td style="padding:12px 16px;font-size:14px;color:${cIdx === 0 ? "#ffffff" : "#cbd5e1"};font-weight:${cIdx === 0 ? "600" : "400"};">${escapeHtml(cell)}</td>`).join("")}
      </tr>
    `).join("");

    bodyHtml = `
      <div>
        ${slide.narrative ? `
          <div style="margin-bottom:18px;font-size:16px;color:#cbd5e1;line-height:1.5;">
            ${parseFormattedText(slide.narrative, brandColor)}
          </div>
        ` : ""}
        <div style="background:${cardBg};border:1px solid ${cardBorder};border-radius:18px;padding:24px;overflow-x:auto;box-shadow:0 8px 24px rgba(0,0,0,0.3);">
          <table style="width:100%;border-collapse:collapse;text-align:left;">
            <thead>
              <tr style="border-bottom:1px solid rgba(255,255,255,0.12);">
                ${tableHeaders.map(h => `
                  <th style="padding:12px 16px;font-size:13px;font-weight:700;color:${brandColor};text-transform:uppercase;letter-spacing:0.04em;">${escapeHtml(h)}</th>
                `).join("")}
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>
    `;
  }

  return `
    <div class="slide ${index === 0 ? "active visible" : ""}" data-index="${index}" style="position:absolute;inset:0;width:1920px;height:1080px;box-sizing:border-box;padding:64px 70px;background:${theme.slide_bg || "#0f172a"};color:${theme.primary_text || "#f8fafc"};">
      ${headerHtml}
      <div style="margin-top:10px;">${bodyHtml}</div>
      ${footerHtml}
    </div>
  `;
}
