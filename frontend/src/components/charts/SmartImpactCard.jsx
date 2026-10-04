import React, { useState } from 'react';
import { AlertTriangle, TrendingDown, DollarSign, Users, ChevronDown, ChevronUp, ShieldAlert } from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';

export default function SmartImpactCard({ impact, className = "", compact = false }) {
  const { isDark } = useTheme();
  const [showFormula, setShowFormula] = useState(false);

  if (!impact) return null;

  const risk = (impact.risk_level || "MODERATE").toUpperCase();
  const isCritical = risk.includes("CRITICAL");
  const isHigh = risk.includes("HIGH") && !isCritical;

  const badgeColor = isCritical
    ? { bg: isDark ? "rgba(239, 68, 68, 0.2)" : "#fee2e2", text: isDark ? "#fca5a5" : "#b91c1c", border: "#ef4444" }
    : isHigh
    ? { bg: isDark ? "rgba(245, 158, 11, 0.2)" : "#fef3c7", text: isDark ? "#fcd34d" : "#b45309", border: "#f59e0b" }
    : { bg: isDark ? "rgba(16, 185, 129, 0.2)" : "#d1fae5", text: isDark ? "#6ee7b7" : "#047857", border: "#10b981" };

  return (
    <div
      className={`smart-impact-card ${className}`}
      style={{
        background: isDark
          ? "linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%)"
          : "linear-gradient(135deg, #ffffff 0%, #f8fafc 100%)",
        border: `1px solid ${isDark ? "rgba(255, 255, 255, 0.1)" : "#e2e8f0"}`,
        borderLeft: `4px solid ${badgeColor.border}`,
        borderRadius: "10px",
        padding: compact ? "10px 14px" : "14px 18px",
        boxShadow: isDark
          ? "0 4px 14px rgba(0, 0, 0, 0.25)"
          : "0 4px 12px rgba(0, 0, 0, 0.05)",
        backdropFilter: "blur(8px)",
        marginBottom: "12px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", marginBottom: "6px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              padding: "2px 8px",
              borderRadius: "999px",
              fontSize: "11px",
              fontWeight: 700,
              letterSpacing: "0.04em",
              backgroundColor: badgeColor.bg,
              color: badgeColor.text,
              border: `1px solid ${badgeColor.border}`,
            }}
          >
            {isCritical ? <ShieldAlert size={12} /> : <AlertTriangle size={12} />}
            {risk} BUSINESS IMPACT
          </span>
          <span
            style={{
              fontSize: "12px",
              fontWeight: 600,
              color: isDark ? "#94a3b8" : "#64748b",
              textTransform: "uppercase",
              letterSpacing: "0.03em"
            }}
          >
            {impact.primary_metric || "Verified Metric"}
          </span>
        </div>

        {impact.affected_population != null && (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "4px",
              fontSize: "12px",
              color: isDark ? "#cbd5e1" : "#475569",
            }}
          >
            <Users size={13} />
            <span>n = {impact.affected_population}</span>
          </span>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", flexWrap: "wrap", gap: "10px", margin: "4px 0" }}>
        <div
          style={{
            fontSize: compact ? "1.25rem" : "1.6rem",
            fontWeight: 800,
            color: isCritical ? (isDark ? "#f87171" : "#dc2626") : (isDark ? "#38bdf8" : "#0284c7"),
            letterSpacing: "-0.02em",
          }}
        >
          {impact.formatted_amount || (impact.amount != null ? `${impact.unit || "$"}${Number(impact.amount).toLocaleString()}` : "—")}
        </div>
      </div>

      {impact.headline && (
        <p
          style={{
            margin: "4px 0 6px 0",
            fontSize: compact ? "12px" : "13.5px",
            lineHeight: 1.45,
            color: isDark ? "#e2e8f0" : "#1e293b",
            fontWeight: 500,
          }}
        >
          {impact.headline}
        </p>
      )}

      {impact.formula_explanation && (
        <div style={{ marginTop: "6px" }}>
          <button
            type="button"
            onClick={() => setShowFormula(prev => !prev)}
            style={{
              background: "transparent",
              border: "none",
              padding: 0,
              fontSize: "11px",
              color: isDark ? "#94a3b8" : "#64748b",
              display: "inline-flex",
              alignItems: "center",
              gap: "3px",
              cursor: "pointer",
              fontWeight: 500,
            }}
          >
            {showFormula ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {showFormula ? "Hide calculation basis" : "View calculation formula"}
          </button>
          {showFormula && (
            <div
              style={{
                marginTop: "4px",
                padding: "6px 10px",
                borderRadius: "6px",
                backgroundColor: isDark ? "rgba(0, 0, 0, 0.3)" : "#f1f5f9",
                fontSize: "11.5px",
                color: isDark ? "#cbd5e1" : "#334155",
                fontFamily: "monospace",
                lineHeight: 1.4,
              }}
            >
              {impact.formula_explanation}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
