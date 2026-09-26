import React, { useState } from "react";
import { Info, Volume2, ChevronDown, ChevronUp, ShieldCheck } from "lucide-react";
import AnimatedAcousticOrb from "../presentation/AnimatedAcousticOrb";
import VoiceoverPlayer from "../VoiceoverPlayer";

export default function ExecutiveBriefingCard({ briefing, snapshot, onInspect }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);

  if (!briefing || briefing.kind === "briefing_unavailable") {
    return null;
  }

  const claimCount = briefing.claims?.length || 0;
  const identity = `${snapshot}:${briefing.calculation_ids?.join("-") || "briefing"}`;

  return (
    <section
      className="adaptive-briefing-card"
      aria-label="Executive briefing"
    >
      <div className="briefing-layout-grid">
        {/* Left Column: Animated Acoustic Orb & Playback Status */}
        <div className="briefing-orb-col">
          <div className="briefing-orb-container">
            <AnimatedAcousticOrb isPlaying={isPlaying} />
          </div>
          <div className="briefing-playback-status" aria-live="polite">
            {isPlaying ? (
              <span className="status-pill status-speaking">
                <span className="status-pulse-dot" aria-hidden="true" />
                <span>Speaking</span>
              </span>
            ) : (
              <span className="status-pill status-ready">
                <span>Ready to listen</span>
              </span>
            )}
          </div>
        </div>

        {/* Right Column: Narrative, Voice Player, and Evidence Accordion */}
        <div className="briefing-content-col">
          <div className="briefing-header">
            <div className="briefing-title-group">
              <span className="briefing-kicker">Executive briefing</span>
              <h2 className="briefing-title">{briefing.title}</h2>
              <p className="briefing-context">{briefing.context_line}</p>
            </div>

            {onInspect && (
              <button
                type="button"
                className="briefing-inspect-btn"
                onClick={() => onInspect("briefing", briefing.inspect)}
                aria-label="Inspect executive briefing calculation and claims"
                title="Inspect executive briefing evidence and calculations"
              >
                <Info size={16} aria-hidden="true" />
              </button>
            )}
          </div>

          {/* Core Written Executive Briefing */}
          <div className="briefing-narrative-box">
            <p className="briefing-spoken-text">{briefing.spoken_text}</p>
          </div>

          {/* Voice Player & Transcript Controls */}
          <div className="briefing-controls-row">
            <div className="briefing-player-wrap">
              <VoiceoverPlayer
                text={briefing.spoken_text}
                identity={identity}
                onPlayingChange={setIsPlaying}
                label="Listen to briefing"
              />
            </div>

            <button
              type="button"
              className="briefing-transcript-toggle"
              onClick={() => setShowTranscript((prev) => !prev)}
              aria-expanded={showTranscript}
              aria-controls="briefing-transcript-panel"
            >
              <span>{showTranscript ? "Hide transcript" : `View transcript (${claimCount} claims)`}</span>
              {showTranscript ? <ChevronUp size={14} aria-hidden="true" /> : <ChevronDown size={14} aria-hidden="true" />}
            </button>
          </div>

          {/* Accessible Claim-by-Claim Transcript Panel */}
          {showTranscript && (
            <div id="briefing-transcript-panel" className="briefing-transcript-panel" role="region" aria-label="Evidence-bound claims">
              <div className="transcript-claims-list">
                {briefing.claims.map((claim, idx) => (
                  <div key={claim.claim_id || idx} className="transcript-claim-item">
                    <div className="claim-item-header">
                      <span className={`claim-type-badge type-${claim.claim_type}`}>
                        {claim.claim_type.replace("_", " ")}
                      </span>
                      <span className="claim-source-tag">Source: {claim.source_component_id}</span>
                    </div>
                    <p className="claim-text">{claim.text}</p>
                    {claim.calculation_ids?.length > 0 && (
                      <div className="claim-calcs">
                        <span className="calc-label">Calculations:</span>{" "}
                        <code>{claim.calculation_ids.join(", ")}</code>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Speech Privacy & Engine Note */}
          <div className="briefing-footer-note">
            <ShieldCheck size={13} aria-hidden="true" />
            <span>Local speech synthesis · Text never leaves this server · Strictly evidence-grounded</span>
          </div>
        </div>
      </div>
    </section>
  );
}
