import React from "react";

export const EVIDENCE_TAG_STYLES = {
  "[Evidence]": { bg: "rgba(16, 185, 129, 0.16)", text: "#10b981", border: "rgba(16, 185, 129, 0.35)" },
  "[Derived Metric]": { bg: "rgba(59, 130, 246, 0.16)", text: "#60a5fa", border: "rgba(59, 130, 246, 0.35)" },
  "[Interpretation]": { bg: "rgba(168, 85, 247, 0.16)", text: "#c084fc", border: "rgba(168, 85, 247, 0.35)" },
  "[Hypothesis]": { bg: "rgba(245, 158, 11, 0.16)", text: "#fbbf24", border: "rgba(245, 158, 11, 0.35)" },
  "[Data Limitation]": { bg: "rgba(239, 68, 68, 0.16)", text: "#f87171", border: "rgba(239, 68, 68, 0.35)" },
  "[Open Question]": { bg: "rgba(234, 179, 8, 0.16)", text: "#facc15", border: "rgba(234, 179, 8, 0.35)" },
  "[Recommendation]": { bg: "rgba(14, 165, 233, 0.16)", text: "#38bdf8", border: "rgba(14, 165, 233, 0.35)" }
};

// Safe inline Markdown parser for **bold** text runs and [Evidence] semantic tag badges
export default function FormattedText({ text, defaultColor }) {
  if (!text) return null;
  // Match both **bold** and [Tags]
  const parts = String(text).split(/(\*\*[^*]+\*\*|\[(?:Evidence|Derived Metric|Interpretation|Hypothesis|Data Limitation|Open Question|Recommendation)\])/g);
  return (
    <span>
      {parts.map((part, idx) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={idx} style={{ fontWeight: 700, color: "var(--brand-color, #ff8a62)" }}>
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (EVIDENCE_TAG_STYLES[part]) {
          const s = EVIDENCE_TAG_STYLES[part];
          return (
            <span
              key={idx}
              style={{
                display: "inline-flex",
                alignItems: "center",
                padding: "1px 7px",
                marginRight: "6px",
                borderRadius: "9999px",
                fontSize: "0.76em",
                fontWeight: 700,
                letterSpacing: "0.03em",
                backgroundColor: s.bg,
                color: s.text,
                border: `1px solid ${s.border}`,
                verticalAlign: "baseline"
              }}
            >
              {part}
            </span>
          );
        }
        return <span key={idx} style={{ color: defaultColor }}>{part}</span>;
      })}
    </span>
  );
}
