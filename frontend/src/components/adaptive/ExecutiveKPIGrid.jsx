import React from "react";
import { Info } from "lucide-react";

/**
 * Governed Executive KPI Grid using semantic definition-list `<dl>`, `<dt>`, `<dd>` markup.
 * Fully keyboard accessible for evidence audit modal inspection.
 */
export default function ExecutiveKPIGrid({
  kpis = [],
  onSelectKpi,
  themeTokens,
  isDark = false,
}) {
  if (!kpis || kpis.length === 0) return null;

  return (
    <dl
      className="executive-kpi-grid"
      role="region"
      aria-label="Executive KPI Overview"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
        gap: "12px",
        margin: 0,
        padding: 0,
      }}
    >
      {kpis.map((kpi, idx) => (
        <div
          key={kpi.kpi_id || idx}
          className="kpi-card"
          data-testid={`kpi-card-${kpi.kpi_id}`}
          role="button"
          tabIndex={0}
          onClick={() => onSelectKpi && onSelectKpi(kpi)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onSelectKpi && onSelectKpi(kpi);
            }
          }}
          aria-label={`Inspect ${kpi.label} audit details`}
          style={{
            backgroundColor: themeTokens?.colors?.surface,
            border: `1px solid ${themeTokens?.colors?.borderSubtle}`,
            borderRadius: "10px",
            padding: "14px 16px",
            cursor: "pointer",
            transition: "transform 0.15s ease, box-shadow 0.15s ease",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div
            className="kpi-header"
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
            }}
          >
            <dt
              className="kpi-label"
              style={{
                fontSize: "0.74rem",
                fontWeight: 600,
                color: themeTokens?.colors?.textSecondary,
                textTransform: "uppercase",
                letterSpacing: "0.03em",
                margin: 0,
              }}
            >
              {kpi.label}
            </dt>
            <Info
              size={12}
              className="kpi-info-icon"
              color={themeTokens?.colors?.textMuted}
              aria-hidden="true"
            />
          </div>

          <div
            className="kpi-metric-row"
            style={{
              margin: "6px 0 2px 0",
              display: "flex",
              alignItems: "baseline",
              gap: "6px",
            }}
          >
            <dd
              className="kpi-value"
              style={{
                fontSize: "1.45rem",
                fontWeight: 800,
                color: themeTokens?.colors?.textPrimary,
                letterSpacing: "-0.02em",
                margin: 0,
              }}
            >
              {kpi.formatted_value || `${kpi.value}${kpi.unit || ""}`}
            </dd>
            {kpi.variance && (
              <span
                className={`kpi-variance ${
                  kpi.variance.startsWith("+")
                    ? "kpi-variance--positive"
                    : "kpi-variance--negative"
                }`}
                style={{
                  fontSize: "0.76rem",
                  fontWeight: 600,
                  color: kpi.variance.startsWith("+")
                    ? themeTokens?.colors?.statusSuccess || "#10b981"
                    : themeTokens?.colors?.statusError || "#ef4444",
                }}
              >
                {kpi.variance}
              </span>
            )}
          </div>

          <div
            className="kpi-subtext"
            style={{
              fontSize: "0.72rem",
              color: themeTokens?.colors?.textMuted,
            }}
          >
            {kpi.subtext || `Audited across ${kpi.population || "all"} records`}
          </div>
        </div>
      ))}
    </dl>
  );
}
