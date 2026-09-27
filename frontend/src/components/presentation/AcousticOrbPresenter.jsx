import React, { useState } from "react";
import { Minimize2, Sparkles, Volume2 } from "lucide-react";
import AnimatedAcousticOrb from "./AnimatedAcousticOrb";
import VoiceoverPlayer from "../VoiceoverPlayer";
import { speakHridayIntro, HRIDAY_ACRONYM } from "../../utils/hridayVoice";
import "../../styles/acoustic-orb.scss";

export default function AcousticOrbPresenter({ deckId, deckSpec, currentSlideOrder = 1 }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [isIntroSpeaking, setIsIntroSpeaking] = useState(false);

  const slide = deckSpec?.slides?.[currentSlideOrder - 1];
  const text = [
    slide?.title,
    slide?.narration_script || slide?.narrative,
    ...(slide?.bullets || []).map((b) => (typeof b === "string" ? b : b.text || "")),
  ]
    .filter(Boolean)
    .join(". ");

  const handlePlayIntro = () => {
    setIsIntroSpeaking(true);
    setIsPlaying(true);
    speakHridayIntro(
      () => {
        setIsIntroSpeaking(true);
        setIsPlaying(true);
      },
      () => {
        setIsIntroSpeaking(false);
        setIsPlaying(false);
      }
    );
  };

  return (
    <div className={`acoustic-orb-presenter hriday-heart-presenter ${expanded ? "expanded" : "minimized"}`}>
      {!expanded && (
        <button
          className="orb-trigger-btn hriday-heart-trigger"
          onClick={() => setExpanded(true)}
          aria-label="Open HRIDAY AI Heart presentation voiceover"
          title="HRIDAY: Human Reasoning Intelligence, Dedicated to Assisting You"
        >
          <span className="mini-canvas-wrap">
            <AnimatedAcousticOrb compact isPlaying={isPlaying || isIntroSpeaking} />
          </span>
          <span className="orb-badge-label">
            <span className="title">HRIDAY AI Heart</span>
            <span className="status">
              <span className="pulse-dot" />
              {isPlaying || isIntroSpeaking ? "Speaking…" : "HRIDAY"}
            </span>
          </span>
        </button>
      )}

      <div className="orb-hud-card hriday-hud-card" style={{ display: expanded ? undefined : "none" }}>
        <div className="orb-hud-header">
          <div className="hud-title-wrap">
            <span className="hud-title">HRIDAY • Slide {currentSlideOrder} Voiceover</span>
            <span className="hud-acronym">{HRIDAY_ACRONYM}</span>
          </div>
          <button
            className="icon-btn"
            aria-label="Minimize HRIDAY voiceover"
            onClick={() => setExpanded(false)}
          >
            <Minimize2 size={16} />
          </button>
        </div>

        {expanded && (
          <div className="orb-visualizer-stage hriday-heart-stage">
            <div className="orb-frequency-glow hriday-heart-glow" />
            <AnimatedAcousticOrb isPlaying={isPlaying || isIntroSpeaking} />
          </div>
        )}

        <div style={{ padding: 16 }}>
          <div className="hriday-intro-action-row" style={{ marginBottom: 12 }}>
            <button
              type="button"
              className="btn-hriday-intro-pill"
              onClick={handlePlayIntro}
              disabled={isIntroSpeaking}
              title="Listen to HRIDAY's spoken introduction and philosophy"
            >
              <Sparkles size={13} />
              <span>{isIntroSpeaking ? "HRIDAY Speaking…" : "Play HRIDAY Introduction"}</span>
            </button>
          </div>

          <p style={{ fontSize: ".8rem", color: "#94a3b8" }}>
            Autonomous device voiceover · Reads the verified boardroom slide
          </p>

          <VoiceoverPlayer
            onPlayingChange={setIsPlaying}
            text={text}
            identity={`${deckId}:${currentSlideOrder}`}
            label="Play slide voiceover"
          />

          <details style={{ marginTop: 12, fontSize: ".8rem" }}>
            <summary>Slide Transcript</summary>
            <p>{text}</p>
          </details>
        </div>
      </div>
    </div>
  );
}
