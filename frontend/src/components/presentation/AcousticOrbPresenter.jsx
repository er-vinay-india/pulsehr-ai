import React, { useState, useEffect, useRef } from "react";
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Volume2, 
  VolumeX, 
  ChevronRight, 
  ChevronLeft, 
  Minimize2, 
  Maximize2, 
  Radio, 
  Sparkles,
  FastForward
} from "lucide-react";
import { getDeckNarration, generateDeckNarration } from "../../api/client";
import "../../styles/acoustic-orb.scss";

export default function AcousticOrbPresenter({
  deckId,
  deckSpec,
  currentSlideOrder = 1,
  totalSlides = 1,
  onAdvanceSlide,
  onPrevSlide
}) {
  const [manifest, setManifest] = useState(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [handsFree, setHandsFree] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [selectedVoice, setSelectedVoice] = useState("andrew");
  const [isExpanded, setIsExpanded] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [audioError, setAudioError] = useState(null);

  const audioRef = useRef(null);
  const canvasRef = useRef(null);
  const miniCanvasRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const sourceNodeRef = useRef(null);
  const animFrameIdRef = useRef(null);
  const rotationRef = useRef(0);
  const waveOffsetRef = useRef(0);

  // 1. Fetch or check narration manifest
  useEffect(() => {
    if (!deckId) return;
    let isMounted = true;
    setLoading(true);
    getDeckNarration(deckId)
      .then((data) => {
        if (isMounted) {
          setManifest(data);
          if (data.voice?.id) {
            const matchKey = Object.entries({
              andrew: "en-US-AndrewMultilingualNeural",
              ryan: "en-GB-RyanNeural",
              ava: "en-US-AvaNeural",
              brian: "en-US-BrianNeural"
            }).find(([, id]) => id === data.voice.id);
            if (matchKey) setSelectedVoice(matchKey[0]);
          }
        }
      })
      .catch((err) => {
        console.warn("Could not check narration manifest:", err);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [deckId]);

  // 2. Generate Narration Handler
  const handleGenerateNarration = async (voiceKey = selectedVoice) => {
    if (!deckId || generating) return;
    setGenerating(true);
    setAudioError(null);
    try {
      const newManifest = await generateDeckNarration(deckId, voiceKey);
      setManifest(newManifest);
      setIsExpanded(true);
    } catch (err) {
      setAudioError(err.message || "Failed to generate narration");
    } finally {
      setGenerating(false);
    }
  };

  // 3. Audio Context & Analyser setup
  const initAudioContext = () => {
    if (!audioRef.current || audioContextRef.current) return;
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      const ctx = new AudioContextClass();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      analyser.smoothingTimeConstant = 0.8;

      const source = ctx.createMediaElementSource(audioRef.current);
      source.connect(analyser);
      analyser.connect(ctx.destination);

      audioContextRef.current = ctx;
      analyserRef.current = analyser;
      sourceNodeRef.current = source;
    } catch (e) {
      console.debug("AudioContext setup:", e);
    }
  };

  // 4. Handle Slide Audio Change
  const currentSlideInfo = manifest?.slides?.find((s) => s.order === currentSlideOrder);
  const currentAudioUrl = currentSlideInfo?.audio_url;

  useEffect(() => {
    if (!audioRef.current || !manifest || manifest.status !== "ready") return;
    if (currentAudioUrl) {
      audioRef.current.src = currentAudioUrl;
      audioRef.current.playbackRate = playbackSpeed;
      if (isPlaying) {
        audioRef.current.play().catch((err) => {
          console.debug("Autoplay prevented:", err);
          setIsPlaying(false);
        });
      }
    }
  }, [currentSlideOrder, currentAudioUrl, manifest]);

  // Play / Pause toggle
  const togglePlay = () => {
    if (!audioRef.current) return;
    initAudioContext();
    if (audioContextRef.current?.state === "suspended") {
      audioContextRef.current.resume();
    }

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch((err) => {
          setAudioError("Audio playback was blocked. Click play again.");
          setIsPlaying(false);
        });
    }
  };

  // Audio event listeners
  const onTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
      setDuration(audioRef.current.duration || currentSlideInfo?.duration_seconds || 0);
    }
  };

  const onAudioEnded = () => {
    setIsPlaying(false);
    if (handsFree && onAdvanceSlide && currentSlideOrder < totalSlides) {
      setTimeout(() => {
        onAdvanceSlide();
        setIsPlaying(true);
      }, 600);
    }
  };

  const handleSeek = (e) => {
    const bar = e.currentTarget;
    const rect = bar.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, clickX / rect.width));
    if (audioRef.current && duration > 0) {
      audioRef.current.currentTime = pct * duration;
    }
  };

  const handleSpeedCycle = () => {
    const speeds = [1.0, 1.25, 1.5];
    const nextIdx = (speeds.indexOf(playbackSpeed) + 1) % speeds.length;
    const nextSpeed = speeds[nextIdx];
    setPlaybackSpeed(nextSpeed);
    if (audioRef.current) {
      audioRef.current.playbackRate = nextSpeed;
    }
  };

  // 5. Canvas Animation Rendering: Luxury Floating Acoustic Orb
  useEffect(() => {
    let active = true;

    const render = () => {
      if (!active) return;
      rotationRef.current += 0.015;
      waveOffsetRef.current += 0.04;

      let freqAmplitude = 0;
      if (analyserRef.current && isPlaying) {
        const buffer = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(buffer);
        let sum = 0;
        for (let i = 0; i < buffer.length; i++) sum += buffer[i];
        freqAmplitude = (sum / buffer.length) / 255; // 0 to 1
      }

      // Draw Main Canvas
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;
        const cx = w / 2;
        const cy = h / 2;
        ctx.clearRect(0, 0, w, h);

        const orbRadius = 40;
        const pulseExpand = freqAmplitude * 20;

        // A. Dynamic Waveform Rings (Gyroscopic)
        const ringCount = 3;
        for (let r = 0; r < ringCount; r++) {
          const ringRadius = orbRadius + 14 + r * 10 + pulseExpand * (r + 1) * 0.5;
          const angleOffset = rotationRef.current * (r % 2 === 0 ? 1 : -0.8) + (r * Math.PI) / 3;
          
          ctx.save();
          ctx.translate(cx, cy);
          ctx.rotate(angleOffset);
          ctx.scale(1, 0.45 + r * 0.1);

          ctx.beginPath();
          // Draw undulating wave along the ellipse
          const segments = 60;
          for (let s = 0; s <= segments; s++) {
            const theta = (s / segments) * Math.PI * 2;
            const wave = Math.sin(theta * 6 + waveOffsetRef.current * 2) * (freqAmplitude * 6 + 1.5);
            const x = (ringRadius + wave) * Math.cos(theta);
            const y = (ringRadius + wave) * Math.sin(theta);
            if (s === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.closePath();

          ctx.lineWidth = 1.5 + freqAmplitude * 2;
          ctx.strokeStyle = r === 0 
            ? `rgba(56, 189, 248, ${0.4 + freqAmplitude * 0.6})` 
            : r === 1
            ? `rgba(245, 158, 11, ${0.35 + freqAmplitude * 0.55})`
            : `rgba(168, 85, 247, ${0.3 + freqAmplitude * 0.5})`;
          ctx.shadowBlur = 10 + freqAmplitude * 20;
          ctx.shadowColor = r === 0 ? "#38bdf8" : "#f59e0b";
          ctx.stroke();
          ctx.restore();
        }

        // B. Deep 3D Shaded Obsidian Core
        const coreGradient = ctx.createRadialGradient(
          cx - orbRadius * 0.35,
          cy - orbRadius * 0.35,
          orbRadius * 0.1,
          cx,
          cy,
          orbRadius
        );
        coreGradient.addColorStop(0, "#334155");
        coreGradient.addColorStop(0.35, "#1e293b");
        coreGradient.addColorStop(0.75, "#0f172a");
        coreGradient.addColorStop(1, "#020617");

        ctx.beginPath();
        ctx.arc(cx, cy, orbRadius, 0, Math.PI * 2);
        ctx.fillStyle = coreGradient;
        ctx.shadowBlur = 18 + freqAmplitude * 25;
        ctx.shadowColor = freqAmplitude > 0.1 ? "rgba(56, 189, 248, 0.7)" : "rgba(15, 23, 42, 0.8)";
        ctx.fill();

        // C. Equator Glow Trench
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(rotationRef.current * 0.5);
        ctx.scale(1, 0.28);
        ctx.beginPath();
        ctx.arc(0, 0, orbRadius * 0.98, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(56, 189, 248, ${0.4 + freqAmplitude * 0.6})`;
        ctx.lineWidth = 2 + freqAmplitude * 4;
        ctx.shadowBlur = 12 + freqAmplitude * 15;
        ctx.shadowColor = "#38bdf8";
        ctx.stroke();
        ctx.restore();

        // D. Specular Glass Highlight
        const specGrad = ctx.createRadialGradient(
          cx - orbRadius * 0.4,
          cy - orbRadius * 0.45,
          0,
          cx - orbRadius * 0.4,
          cy - orbRadius * 0.45,
          orbRadius * 0.45
        );
        specGrad.addColorStop(0, "rgba(255, 255, 255, 0.75)");
        specGrad.addColorStop(0.5, "rgba(255, 255, 255, 0.15)");
        specGrad.addColorStop(1, "transparent");

        ctx.beginPath();
        ctx.arc(cx - orbRadius * 0.4, cy - orbRadius * 0.45, orbRadius * 0.45, 0, Math.PI * 2);
        ctx.fillStyle = specGrad;
        ctx.shadowBlur = 0;
        ctx.fill();
      }

      // Draw Mini Canvas (for Trigger Icon)
      const miniCanvas = miniCanvasRef.current;
      if (miniCanvas) {
        const mCtx = miniCanvas.getContext("2d");
        const mw = miniCanvas.width;
        const mh = miniCanvas.height;
        mCtx.clearRect(0, 0, mw, mh);
        const mcx = mw / 2;
        const mcy = mh / 2;

        // Mini Core
        mCtx.beginPath();
        mCtx.arc(mcx, mcy, 12, 0, Math.PI * 2);
        mCtx.fillStyle = isPlaying ? "#0284c7" : "#1e293b";
        mCtx.shadowBlur = isPlaying ? 10 : 3;
        mCtx.shadowColor = "#38bdf8";
        mCtx.fill();

        // Mini Ring
        mCtx.beginPath();
        mCtx.arc(mcx, mcy, 15, 0, Math.PI * 2);
        mCtx.strokeStyle = isPlaying ? "rgba(56, 189, 248, 0.8)" : "rgba(255, 255, 255, 0.2)";
        mCtx.lineWidth = 1.5;
        mCtx.stroke();
      }

      animFrameIdRef.current = requestAnimationFrame(render);
    };

    render();
    return () => {
      active = false;
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
    };
  }, [isPlaying]);

  const hasNarration = manifest && manifest.status === "ready";

  return (
    <div className={`acoustic-orb-presenter ${isExpanded ? "expanded" : "minimized"}`}>
      {/* Hidden Audio Element */}
      <audio
        ref={audioRef}
        onTimeUpdate={onTimeUpdate}
        onEnded={onAudioEnded}
        muted={isMuted}
        crossOrigin="anonymous"
      />

      {/* MINIMIZED TRIGGER BUTTON */}
      {!isExpanded && (
        <button
          className="orb-trigger-btn"
          onClick={() => setIsExpanded(true)}
          title="Open Acoustic Executive AI Presenter"
        >
          <div className="mini-canvas-wrap">
            <canvas ref={miniCanvasRef} width={38} height={38} />
          </div>
          <div className="orb-badge-label">
            <span className="title">Executive AI Orb</span>
            <span className="status">
              <span className="pulse-dot" />
              {isPlaying ? "Speaking..." : hasNarration ? "Ready" : "Voiceover"}
            </span>
          </div>
        </button>
      )}

      {/* EXPANDED EXECUTIVE PRESENTER HUD */}
      {isExpanded && (
        <div className="orb-hud-card">
          {/* Header */}
          <div className="orb-hud-header">
            <div className="hud-title-group">
              <Sparkles className="insignia-icon" />
              <span className="hud-title">Executive AI Orb</span>
              <span className="live-tag">Briefing</span>
            </div>
            <div className="header-actions">
              <button
                className="icon-btn"
                onClick={() => setIsExpanded(false)}
                title="Minimize to Orb badge"
              >
                <Minimize2 size={15} />
              </button>
            </div>
          </div>

          {/* Visualizer Stage */}
          <div className="orb-visualizer-stage">
            <div className="orb-frequency-glow" />
            <canvas ref={canvasRef} width={280} height={160} />
          </div>

          {/* Uninitialized State */}
          {!hasNarration && (
            <div style={{ padding: "16px", textAlign: "center" }}>
              <p style={{ fontSize: "0.8rem", color: "#94a3b8", marginBottom: "12px" }}>
                Studio-quality executive voiceover ready for {totalSlides} slides.
              </p>
              <button
                className="pill-btn active"
                style={{
                  width: "100%",
                  padding: "10px",
                  fontSize: "0.82rem",
                  background: "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)",
                  color: "#ffffff",
                  border: "none"
                }}
                onClick={() => handleGenerateNarration(selectedVoice)}
                disabled={generating}
              >
                {generating ? "Synthesizing Executive Voiceover..." : "Initialize AI Presenter"}
              </button>
            </div>
          )}

          {/* Ready Narration State */}
          {hasNarration && (
            <>
              {/* Transcript Box */}
              <div className="orb-transcript-box">
                <p className="transcript-text">
                  "{currentSlideInfo?.transcript || "Preparing slide briefing..."}"
                </p>
              </div>

              {/* Controls Section */}
              <div className="orb-controls-section">
                {/* Timeline Scrubber */}
                <div className="timeline-bar-wrap">
                  <span>
                    {Math.floor(currentTime / 60)}:
                    {String(Math.floor(currentTime % 60)).padStart(2, "0")}
                  </span>
                  <div className="progress-track" onClick={handleSeek}>
                    <div
                      className="progress-fill"
                      style={{
                        width: duration > 0 ? `${(currentTime / duration) * 100}%` : "0%"
                      }}
                    />
                  </div>
                  <span>
                    {Math.floor(duration / 60)}:
                    {String(Math.floor(duration % 60)).padStart(2, "0")}
                  </span>
                </div>

                {/* Playback Controls Row */}
                <div className="playback-row">
                  {/* Left: Toggles */}
                  <div className="left-toggles">
                    <button
                      className={`pill-btn ${handsFree ? "active" : ""}`}
                      onClick={() => setHandsFree(!handsFree)}
                      title="Automatically advance slides when narration finishes"
                    >
                      Auto-Advance
                    </button>
                    <button
                      className="pill-btn"
                      onClick={handleSpeedCycle}
                      title="Cycle playback speed"
                    >
                      {playbackSpeed}x
                    </button>
                  </div>

                  {/* Center: Main Play Controls */}
                  <div className="main-play-group">
                    {onPrevSlide && (
                      <button
                        className="nav-step-btn"
                        onClick={onPrevSlide}
                        disabled={currentSlideOrder <= 1}
                        title="Previous slide"
                      >
                        <ChevronLeft size={16} />
                      </button>
                    )}
                    <button className="play-btn" onClick={togglePlay}>
                      {isPlaying ? <Pause /> : <Play style={{ marginLeft: "2px" }} />}
                    </button>
                    {onAdvanceSlide && (
                      <button
                        className="nav-step-btn"
                        onClick={onAdvanceSlide}
                        disabled={currentSlideOrder >= totalSlides}
                        title="Next slide"
                      >
                        <ChevronRight size={16} />
                      </button>
                    )}
                  </div>

                  {/* Right: Voice selector & Mute */}
                  <div className="voice-select-wrap" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <select
                      value={selectedVoice}
                      onChange={(e) => {
                        const v = e.target.value;
                        setSelectedVoice(v);
                        handleGenerateNarration(v);
                      }}
                      title="Select Executive AI Voice"
                    >
                      <option value="andrew">Andrew (US)</option>
                      <option value="ryan">Ryan (UK)</option>
                      <option value="ava">Ava (US)</option>
                      <option value="brian">Brian (US)</option>
                    </select>
                    <button
                      className="nav-step-btn"
                      onClick={() => setIsMuted(!isMuted)}
                      title={isMuted ? "Unmute" : "Mute"}
                    >
                      {isMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}

          {audioError && (
            <div style={{ padding: "8px 16px", color: "#f87171", fontSize: "0.75rem", background: "rgba(239, 68, 68, 0.1)" }}>
              {audioError}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
