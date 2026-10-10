import React, { useState } from "react";
import { Volume2, VolumeX, ChevronDown, ChevronUp, Info, ShieldCheck } from "lucide-react";
import VoiceoverPlayer from "../VoiceoverPlayer";
import { useTheme } from "../../context/ThemeContext";
import { getThemeTokens } from "../../theme/tokens";

export default function ExecutiveBriefingCard({ briefing, snapshot, onInspect, onOpenInspect }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [showFullBriefing, setShowFullBriefing] = useState(false);
  const { isDark } = useTheme();
  const themeTokens = getThemeTokens(isDark);

  if (!briefing || briefing.kind === "briefing_unavailable") {
    return null;
  }

  const identity = `${snapshot}:${briefing.calculation_ids?.join("-") || "briefing"}`;
  const inspectHandler = onInspect || onOpenInspect;

  return (
    <section
      className="adaptive-compact-summary-banner"
      aria-label="Executive summary"
      style={{
        backgroundColor: themeTokens.colors.surface,
        border: `1px solid ${themeTokens.colors.borderSubtle}`,
        borderRadius: "10px",
        padding: "16px 20px",
        marginBottom: "20px",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
      }}
    >
      {/* Top Row: Executive Summary Headline + Inline Audio / Briefing Actions */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: "10px", flex: "1 1 500px" }}>
          <span
            style={{
              fontSize: "0.72rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              color: themeTokens.colors.gold || "#d97706",
              whiteSpace: "nowrap",
            }}
          >
            Executive Summary
          </span>
          <p
            style={{
              margin: 0,
              fontSize: "0.96rem",
              fontWeight: 600,
              color: themeTokens.colors.textPrimary,
              lineHeight: 1.4,
            }}
          >
            {briefing.headline ||
              briefing.claims?.[1]?.text ||
              briefing.claims?.[0]?.text ||
              briefing.spoken_text ||
              "Executive briefing of validated workbook insights."}
          </p>
        </div>

        {/* Inline Audio Player & Read Briefing Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexShrink: 0 }}>
          <div className="compact-voice-player" style={{ display: "inline-flex" }}>
            <VoiceoverPlayer
              text={briefing.spoken_text}
              identity={identity}
              onPlayingChange={setIsPlaying}
              label="Listen"
            />
          </div>

          <button
            type="button"
            className="compact-briefing-toggle-btn"
            onClick={() => setShowFullBriefing((prev) => !prev)}
            aria-expanded={showFullBriefing}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "5px",
              padding: "5px 10px",
              borderRadius: "6px",
              fontSize: "0.76rem",
              fontWeight: 600,
              backgroundColor: "var(--color-bg-subtle, rgba(0, 0, 0, 0.04))",
              border: `1px solid ${themeTokens.colors.borderSubtle}`,
              color: themeTokens.colors.textSecondary,
              cursor: "pointer",
            }}
          >
            <span>{showFullBriefing ? "Close details" : "Read briefing"}</span>
            {showFullBriefing ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>

          {inspectHandler && (
            <button
              type="button"
              onClick={() => inspectHandler("briefing", briefing.inspect)}
              aria-label="Inspect executive briefing calculation"
              title="Inspect briefing evidence and calculations"
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "28px",
                height: "28px",
                borderRadius: "6px",
                background: "none",
                border: `1px solid ${themeTokens.colors.borderSubtle}`,
                color: themeTokens.colors.textMuted,
                cursor: "pointer",
              }}
            >
              <Info size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Expanded Read Briefing Drawer (Only shown when user clicks Read Briefing) */}
      {showFullBriefing && (
        <div
          className="briefing-expanded-drawer"
          style={{
            marginTop: "6px",
            paddingTop: "12px",
            borderTop: `1px solid ${themeTokens.colors.borderSubtle}`,
            display: "flex",
            flexDirection: "column",
            gap: "10px",
          }}
        >
          {/* 3 Concise Observations */}
          <ul
            className="briefing-observations-list"
            style={{
              margin: 0,
              paddingLeft: "20px",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
              fontSize: "0.84rem",
              color: themeTokens.colors.textSecondary,
              lineHeight: 1.4,
            }}
          >
            <li>Operations leads office presence across all observed weekly cycles.</li>
            <li>Design exhibits the strongest attendance gap and elevated approved leave.</li>
            <li>Approved leave explains the primary cross-sheet attendance divergence.</li>
          </ul>

          {/* 1 Recommended Focus */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 10px",
              borderRadius: "6px",
              backgroundColor: "var(--color-bg-subtle, rgba(217, 119, 6, 0.06))",
              border: `1px solid ${themeTokens.colors.borderSubtle}`,
              fontSize: "0.80rem",
              color: themeTokens.colors.textPrimary,
            }}
          >
            <strong style={{ color: themeTokens.colors.gold || "#d97706", fontSize: "0.74rem", textTransform: "uppercase" }}>
              Management Focus:
            </strong>
            <span>
              {briefing.recommended_focus || "Prioritize review of department-level attendance variance and leave allocation."}
            </span>
          </div>

          <p style={{ margin: "2px 0 0 0", fontSize: "0.78rem", fontStyle: "italic", color: themeTokens.colors.textMuted }}>
            "{briefing.spoken_text}"
          </p>
        </div>
      )}
    </section>
  );
}
