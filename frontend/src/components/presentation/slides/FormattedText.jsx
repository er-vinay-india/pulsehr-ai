import { EVIDENCE_TAG_TOKENS } from '../../../theme/slideTokens.js';
import React from "react";

export const EVIDENCE_TAG_STYLES = Object.fromEntries(Object.entries(EVIDENCE_TAG_TOKENS).map(([tag,token]) => [tag, { bg:'var(--card-bg-alt)', text:`var(--${{success_color:'success-color',brand_color:'brand-color',accent_color:'accent-color',warning_color:'warning-color',danger_color:'danger-color'}[token]})`, border:'var(--card-border)' }]));

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
            <strong key={idx} style={{ fontWeight: 700, color: "var(--brand-color)" }}>
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (EVIDENCE_TAG_STYLES[part.toLowerCase()]) {
          const s = EVIDENCE_TAG_STYLES[part.toLowerCase()];
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
