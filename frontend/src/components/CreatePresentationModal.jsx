import React, { useState, useEffect, useRef } from "react";
import {
  Sparkles,
  Presentation,
  Download,
  X,
  Play,
  RotateCw,
  Sliders,
  CheckCircle2,
  Clock,
  Trash2,
  Copy,
  ArrowUp,
  ArrowDown,
  Plus,
  Edit3,
  Palette,
  FileText,
  AlertTriangle,
  Layers,
  ChevronRight,
  RefreshCw
} from "lucide-react";
import {
  getPresentationThemes,
  startPresentationGeneration,
  getPresentationJob,
  getPresentationDeck,
  cancelPresentationJob,
  getSheets,
  updatePresentationDeck,
  regenerateSlide,
  exportPresentationPptx
} from "../api/client";
import PresentationRevealDeck from "./PresentationRevealDeck.jsx";

const STAGES = [
  { id: "collecting_findings", label: "Collecting Findings", desc: "Capturing verified metrics & dataset snapshot" },
  { id: "planning_outline", label: "Planning Outline", desc: "Structuring domain-aware presentation narrative" },
  { id: "preparing_charts", label: "Preparing Charts", desc: "Extracting Top 10 rankings, trends & KPI metrics" },
  { id: "building_slides", label: "Building Slides", desc: "Assembling executive slide layouts & content runs" },
  { id: "verifying_facts", label: "Verifying Facts", desc: "Auditing deterministic numbers & styling standards" },
  { id: "ready", label: "Ready to Review", desc: "Generating native editable PowerPoint export" }
];

export default function CreatePresentationModal({
  isOpen,
  onClose,
  activeJobId = null,
  initialDeck = null,
  onJobUpdate = () => {}
}) {
  const [viewMode, setViewMode] = useState("config"); // "config" | "generating" | "studio"
  const [themes, setThemes] = useState([]);
  const [sheets, setSheets] = useState([]);

  // Config form state
  const [objective, setObjective] = useState("Executive Leadership Review");
  const [audience, setAudience] = useState("C-Suite & Operations Leadership");
  const [targetLength, setTargetLength] = useState(6);
  const [selectedThemeId, setSelectedThemeId] = useState("executive_dark");
  const [selectedSheetId, setSelectedSheetId] = useState("");
  const [instructions, setInstructions] = useState("");
  const [autoDownload, setAutoDownload] = useState(true);

  // Job progress state
  const [currentJobId, setCurrentJobId] = useState(activeJobId);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobStage, setJobStage] = useState("collecting_findings");
  const [jobStageLabel, setJobStageLabel] = useState("Initiating pipeline...");
  const [jobError, setJobError] = useState(null);

  // Studio deck state
  const [deckSpec, setDeckSpec] = useState(initialDeck);
  const [activeSlideIndex, setActiveSlideIndex] = useState(0);
  const [isExportingPptx, setIsExportingPptx] = useState(false);
  const [isRegeneratingSlide, setIsRegeneratingSlide] = useState(false);
  const [regeneratePrompt, setRegeneratePrompt] = useState("");
  const [showRegenModal, setShowRegenModal] = useState(false);
  const [speakerNotesOpen, setSpeakerNotesOpen] = useState(true);

  // Poll timer
  const pollTimerRef = useRef(null);

  // 1. Initial data fetch
  useEffect(() => {
    if (!isOpen) return;

    getPresentationThemes()
      .then(res => {
        if (res.themes) setThemes(res.themes);
      })
      .catch(console.error);

    getSheets()
      .then(res => {
        if (res.sheets && res.sheets.length > 0) {
          setSheets(res.sheets);
          if (!selectedSheetId) {
            setSelectedSheetId(String(res.sheets[0].id));
          }
        }
      })
      .catch(console.error);
  }, [isOpen]);

  // 2. Initial viewMode determination
  useEffect(() => {
    if (initialDeck) {
      setDeckSpec(initialDeck);
      setViewMode("studio");
    } else if (activeJobId) {
      setCurrentJobId(activeJobId);
      setViewMode("generating");
    }
  }, [initialDeck, activeJobId]);

  // 3. Polling for background job
  useEffect(() => {
    if (viewMode !== "generating" || !currentJobId) return;

    let isMounted = true;

    const poll = async () => {
      try {
        const job = await getPresentationJob(currentJobId);
        if (!isMounted) return;

        onJobUpdate(job);
        setJobProgress(job.progress_pct || 0);
        setJobStage(job.stage);
        setJobStageLabel(job.stage_label || "Processing...");

        if (job.status === "ready") {
          let deck = job.deck;
          if (!deck && job.deck_id) {
            try {
              deck = await getPresentationDeck(job.deck_id);
            } catch (deckErr) {
              console.error("Failed to fetch ready deck:", deckErr);
            }
          }

          if (deck) {
            setDeckSpec(deck);
            setViewMode("studio");
            onJobUpdate({ ...job, deck });

            if (autoDownload) {
              try {
                await exportPresentationPptx(deck);
              } catch (dlErr) {
                console.warn("Auto-download PowerPoint failed:", dlErr);
              }
            }
            return;
          }
        }

        if (job.status === "failed") {
          setJobError(job.error || "Generation pipeline encountered an error.");
          return;
        }

        if (job.status === "cancelled") {
          setViewMode("config");
          return;
        }

        pollTimerRef.current = setTimeout(poll, 1500);
      } catch (err) {
        console.error("Job polling error:", err);
        if (isMounted) {
          pollTimerRef.current = setTimeout(poll, 2500);
        }
      }
    };

    poll();

    return () => {
      isMounted = false;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [viewMode, currentJobId, autoDownload]);

  if (!isOpen) return null;

  // Handlers
  const handleStartGeneration = async () => {
    setJobError(null);
    try {
      const scope = {
        objective,
        audience,
        target_length: Number(targetLength),
        theme_id: selectedThemeId,
        sheet_id: selectedSheetId ? Number(selectedSheetId) : null,
        instructions
      };
      const res = await startPresentationGeneration(scope);
      setCurrentJobId(res.job_id);
      setJobProgress(5);
      setJobStage("collecting_findings");
      setJobStageLabel("Initiating presentation generation pipeline...");
      setViewMode("generating");
      onJobUpdate({ ...res, progress_pct: 5 });
    } catch (err) {
      setJobError(err.message || "Failed to start presentation generation");
    }
  };

  const handleCancelGeneration = async () => {
    if (!currentJobId) return;
    try {
      await cancelPresentationJob(currentJobId);
      setViewMode("config");
      setCurrentJobId(null);
      onJobUpdate(null);
    } catch (err) {
      console.error("Cancel job error:", err);
    }
  };

  const handleSwitchTheme = (themeId) => {
    if (!deckSpec) return;
    const matchedTheme = themes.find(t => t.id === themeId);
    if (!matchedTheme) return;

    const updated = {
      ...deckSpec,
      metadata: { ...deckSpec.metadata, theme_id: themeId },
      theme: matchedTheme
    };
    setDeckSpec(updated);
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleUpdateSlide = (slideIndex, updatedSlide) => {
    if (!deckSpec) return;
    const newSlides = [...deckSpec.slides];
    newSlides[slideIndex] = updatedSlide;
    const updated = { ...deckSpec, slides: newSlides };
    setDeckSpec(updated);
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleMoveSlide = (index, direction) => {
    if (!deckSpec) return;
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= deckSpec.slides.length) return;

    const newSlides = [...deckSpec.slides];
    const temp = newSlides[index];
    newSlides[index] = newSlides[newIndex];
    newSlides[newIndex] = temp;
    newSlides.forEach((s, idx) => { s.order = idx + 1; });

    const updated = { ...deckSpec, slides: newSlides };
    setDeckSpec(updated);
    setActiveSlideIndex(newIndex);
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleDeleteSlide = (index) => {
    if (!deckSpec || deckSpec.slides.length <= 1) {
      alert("A presentation must retain at least one slide.");
      return;
    }
    const newSlides = deckSpec.slides.filter((_, i) => i !== index);
    newSlides.forEach((s, idx) => { s.order = idx + 1; });

    const updated = { ...deckSpec, slides: newSlides };
    setDeckSpec(updated);
    setActiveSlideIndex(Math.max(0, Math.min(activeSlideIndex, newSlides.length - 1)));
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleDuplicateSlide = (index) => {
    if (!deckSpec) return;
    const target = deckSpec.slides[index];
    const duplicated = JSON.parse(JSON.stringify(target));
    duplicated.id = `slide_${Date.now()}`;
    duplicated.title = `${duplicated.title} (Copy)`;

    const newSlides = [...deckSpec.slides];
    newSlides.splice(index + 1, 0, duplicated);
    newSlides.forEach((s, idx) => { s.order = idx + 1; });

    const updated = { ...deckSpec, slides: newSlides };
    setDeckSpec(updated);
    setActiveSlideIndex(index + 1);
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleAddSlide = () => {
    if (!deckSpec) return;
    const newSlide = {
      id: `slide_${Date.now()}`,
      order: deckSpec.slides.length + 1,
      layout: "chart_narrative",
      category: "OPERATIONAL HIGHLIGHT",
      title: "New Strategic Slide",
      subtitle: "Operational analysis and key recommendations",
      narrative: "Synthesized observations regarding current dataset throughput and trends.",
      bullets: [
        "First key analytical finding identified from data audit.",
        "Recommended operational next step for leadership review."
      ],
      metrics: [
        { label: "Throughput", value: "Optimal", subtext: "Target range" }
      ],
      chart: null,
      table: null,
      speaker_notes: "Add key talking points and presentation remarks here.",
      evidence_sources: ["PulseHR Ground Truth Engine"]
    };

    const newSlides = [...deckSpec.slides, newSlide];
    const updated = { ...deckSpec, slides: newSlides };
    setDeckSpec(updated);
    setActiveSlideIndex(newSlides.length - 1);
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleRegenerateSlideSubmit = async () => {
    if (!deckSpec || !regeneratePrompt.trim()) return;
    const currentSlide = deckSpec.slides[activeSlideIndex];
    if (!currentSlide) return;

    setIsRegeneratingSlide(true);
    try {
      const updated = await regenerateSlide(deckSpec, currentSlide.id, regeneratePrompt);
      setDeckSpec(updated);
      setShowRegenModal(false);
      setRegeneratePrompt("");
    } catch (err) {
      alert(`Regeneration failed: ${err.message}`);
    } finally {
      setIsRegeneratingSlide(false);
    }
  };

  const handleExportPptx = async () => {
    if (!deckSpec) return;
    setIsExportingPptx(true);
    try {
      await exportPresentationPptx(deckSpec);
    } catch (err) {
      alert(`PowerPoint export failed: ${err.message}`);
    } finally {
      setIsExportingPptx(false);
    }
  };

  const currentTheme = deckSpec?.theme || themes.find(t => t.id === selectedThemeId) || {
    bg_color: "#171412",
    card_bg: "#201b18",
    card_border: "#3d362f",
    primary_text: "#fff9f2",
    secondary_text: "#beb2a6",
    brand_color: "#ff8a62",
    accent_color: "#7ee7d9"
  };

  return (
    <div className="presentation-modal-backdrop" role="dialog" aria-modal="true">
      <div className={`presentation-modal-shell mode-${viewMode}`}>
        {/* MODAL HEADER */}
        <div className="pres-modal-header">
          <div className="header-title-wrap">
            <div className="icon-badge">
              <Presentation size={18} />
            </div>
            <div>
              <h3>
                {viewMode === "config" && "Create AI-Assisted Presentation"}
                {viewMode === "generating" && "Generating Presentation Deck"}
                {viewMode === "studio" && (deckSpec?.metadata?.title || "Presentation Studio")}
              </h3>
              <p className="sub-hint">
                {viewMode === "config" && "Launch a verified, domain-aware presentation with native editable PowerPoint charts"}
                {viewMode === "generating" && "Running 6-stage background analytical intelligence pipeline"}
                {viewMode === "studio" && `${deckSpec?.slides?.length || 0} slides · ${currentTheme?.name || "Theme"} · Reveal.js 16:9 Presenter`}
              </p>
            </div>
          </div>

          <div className="header-actions-row">
            {viewMode === "studio" && (
              <>
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => setShowRegenModal(true)}
                  title="Regenerate current slide with AI prompt"
                >
                  <Sparkles size={14} />
                  <span>Regenerate Slide</span>
                </button>

                <button
                  type="button"
                  className="btn-primary btn-sm"
                  onClick={handleExportPptx}
                  disabled={isExportingPptx}
                  title="Export native editable PowerPoint with charts and notes"
                >
                  <Download size={14} />
                  <span>{isExportingPptx ? "Preparing .PPTX..." : "Download .PPTX"}</span>
                </button>
              </>
            )}

            <button
              type="button"
              className="btn-icon-close"
              onClick={onClose}
              aria-label="Close presentation studio"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* VIEW 1: CONFIGURATION FORM */}
        {viewMode === "config" && (
          <div className="pres-config-body">
            <div className="config-form-grid">
              {/* Left Column: Core Parameters */}
              <div className="config-col">
                <div className="form-group">
                  <label htmlFor="pres-obj">Presentation Objective / Topic</label>
                  <input
                    id="pres-obj"
                    type="text"
                    className="form-input"
                    value={objective}
                    onChange={e => setObjective(e.target.value)}
                    placeholder="e.g. Executive Sales Performance & Seasonal Peak Review"
                  />
                  <div className="quick-suggestions">
                    <button
                      type="button"
                      className="suggestion-tag"
                      onClick={() => setObjective("Executive Store Revenue & Seasonal Sales Variance")}
                    >
                      Sales Variance
                    </button>
                    <button
                      type="button"
                      className="suggestion-tag"
                      onClick={() => setObjective("Operational Throughput & Leader Benchmarks")}
                    >
                      Store Leaderboard
                    </button>
                    <button
                      type="button"
                      className="suggestion-tag"
                      onClick={() => setObjective("Strategic Workforce Distribution & Attendance Review")}
                    >
                      Workforce Plan
                    </button>
                  </div>
                </div>

                <div className="form-row-2">
                  <div className="form-group">
                    <label htmlFor="pres-aud">Target Audience</label>
                    <select
                      id="pres-aud"
                      className="form-select"
                      value={audience}
                      onChange={e => setAudience(e.target.value)}
                    >
                      <option value="C-Suite & Operations Leadership">C-Suite & Operations Leadership</option>
                      <option value="Regional Store & Field Directors">Regional Store & Field Directors</option>
                      <option value="Workforce Planning & People Ops">Workforce Planning & People Ops</option>
                      <option value="Board of Directors & Investors">Board of Directors & Investors</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label htmlFor="pres-len">Target Slide Count</label>
                    <select
                      id="pres-len"
                      className="form-select"
                      value={targetLength}
                      onChange={e => setTargetLength(e.target.value)}
                    >
                      <option value="4">4 Slides (Executive Summary)</option>
                      <option value="6">6 Slides (Standard Briefing)</option>
                      <option value="8">8 Slides (Comprehensive Review)</option>
                      <option value="10">10 Slides (Detailed Deep Dive)</option>
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label htmlFor="pres-sheet">Source Dataset / Sheet</label>
                  <select
                    id="pres-sheet"
                    className="form-select"
                    value={selectedSheetId}
                    onChange={e => setSelectedSheetId(e.target.value)}
                  >
                    {sheets.map(s => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.row_count.toLocaleString()} rows)
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="pres-instr">Additional Focus & Instructions (Optional)</label>
                  <textarea
                    id="pres-instr"
                    className="form-textarea"
                    rows={3}
                    value={instructions}
                    onChange={e => setInstructions(e.target.value)}
                    placeholder="e.g. Focus on holiday promotional lift and inventory replenishment cycles."
                  />
                </div>

                <div className="form-group" style={{ marginTop: "10px" }}>
                  <label style={{ display: "inline-flex", alignItems: "center", gap: "8px", cursor: "pointer", fontSize: "0.82rem", color: "var(--fg-primary)", userSelect: "none" }}>
                    <input
                      type="checkbox"
                      checked={autoDownload}
                      onChange={e => setAutoDownload(e.target.checked)}
                      style={{ width: "16px", height: "16px", cursor: "pointer", accentColor: "var(--brand-400)" }}
                    />
                    <span>Automatically download PowerPoint (.pptx) file when ready</span>
                  </label>
                </div>
              </div>

              {/* Right Column: Visual Theme Selection */}
              <div className="config-col">
                <label className="section-label">Select Visual Presentation Theme</label>
                <div className="themes-card-grid">
                  {themes.map(t => {
                    const isSelected = t.id === selectedThemeId;
                    return (
                      <div
                        key={t.id}
                        className={`theme-card ${isSelected ? "selected" : ""}`}
                        style={{ backgroundColor: t.card_bg, borderColor: isSelected ? t.brand_color : t.card_border }}
                        onClick={() => setSelectedThemeId(t.id)}
                      >
                        <div className="theme-card-top">
                          <span className="theme-name" style={{ color: t.primary_text }}>{t.name}</span>
                          {isSelected && <CheckCircle2 size={16} style={{ color: t.brand_color }} />}
                        </div>

                        {/* Theme Swatches Preview */}
                        <div className="theme-swatch-row">
                          <span className="swatch" style={{ backgroundColor: t.bg_color }} title="Background" />
                          <span className="swatch" style={{ backgroundColor: t.brand_color }} title="Brand" />
                          <span className="swatch" style={{ backgroundColor: t.accent_color }} title="Accent" />
                          <span className="swatch" style={{ backgroundColor: t.success_color }} title="Success" />
                        </div>

                        <div className="theme-preview-box" style={{ backgroundColor: t.bg_color }}>
                          <span className="mini-title" style={{ color: t.brand_color }}>Executive Preview</span>
                          <div className="mini-bar-preview">
                            <span style={{ width: "80%", backgroundColor: t.brand_color }} />
                            <span style={{ width: "55%", backgroundColor: t.accent_color }} />
                            <span style={{ width: "35%", backgroundColor: t.success_color }} />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {jobError && (
                  <div className="pres-error-callout">
                    <AlertTriangle size={16} />
                    <span>{jobError}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="pres-config-footer">
              <div className="footer-left-note">
                <CheckCircle2 size={14} />
                <span>Deterministic SQL ground truth · Native OpenXML PowerPoint charts</span>
              </div>
              <button
                type="button"
                className="btn-primary btn-lg"
                onClick={handleStartGeneration}
              >
                <Sparkles size={18} />
                <span>Generate Presentation</span>
              </button>
            </div>
          </div>
        )}

        {/* VIEW 2: REAL-TIME GENERATION PIPELINE PROGRESS */}
        {viewMode === "generating" && (
          <div className="pres-generating-body">
            <div className="generating-header-card">
              <div className="pipeline-spinner-badge">
                {jobStage === "ready" || jobProgress >= 100 ? (
                  <CheckCircle2 size={28} style={{ color: "var(--brand-400, #ffad85)" }} />
                ) : (
                  <RotateCw size={24} className="spin-icon" />
                )}
              </div>
              <h4>
                {jobStage === "ready" || jobProgress >= 100
                  ? "Presentation Ready!"
                  : "Synthesizing Presentation Intelligence"}
              </h4>
              <p>{jobStageLabel}</p>

              {/* Progress bar */}
              <div className="pipeline-progress-track">
                <div
                  className="pipeline-progress-bar"
                  style={{ width: `${Math.max(5, jobProgress)}%` }}
                />
              </div>
              <span className="pipeline-progress-pct">{jobProgress}% Complete</span>

              {(jobStage === "ready" || jobProgress >= 100) && (
                <div style={{ display: "flex", gap: "10px", marginTop: "16px", justifyContent: "center" }}>
                  <button
                    type="button"
                    className="btn-primary btn-sm"
                    onClick={() => {
                      if (deckSpec) {
                        setViewMode("studio");
                      } else if (currentJobId) {
                        getPresentationJob(currentJobId).then(j => {
                          if (j?.deck) {
                            setDeckSpec(j.deck);
                            setViewMode("studio");
                          } else if (j?.deck_id) {
                            getPresentationDeck(j.deck_id).then(d => {
                              setDeckSpec(d);
                              setViewMode("studio");
                            });
                          }
                        });
                      }
                    }}
                  >
                    <Presentation size={14} />
                    <span>Open in Studio</span>
                  </button>
                  <button
                    type="button"
                    className="btn-secondary btn-sm"
                    onClick={() => {
                      if (deckSpec) {
                        exportPresentationPptx(deckSpec);
                      } else if (currentJobId) {
                        getPresentationJob(currentJobId).then(j => {
                          const did = j?.deck_id;
                          if (did) window.open(`/api/presentations/download/${did}`, "_blank");
                        });
                      }
                    }}
                  >
                    <Download size={14} />
                    <span>Download .PPTX</span>
                  </button>
                </div>
              )}
            </div>

            {/* 6 Stages Stepper */}
            <div className="pipeline-stages-list">
              {STAGES.map((st, idx) => {
                const currentStageIdx = STAGES.findIndex(s => s.id === jobStage);
                const isPassed = currentStageIdx > idx || jobProgress >= 100;
                const isCurrent = jobStage === st.id;

                return (
                  <div
                    key={st.id}
                    className={`pipeline-stage-row ${isPassed ? "completed" : ""} ${isCurrent ? "active" : ""}`}
                  >
                    <div className="stage-status-icon">
                      {isPassed ? (
                        <CheckCircle2 size={18} className="icon-success" />
                      ) : isCurrent ? (
                        <RotateCw size={18} className="icon-active spin-icon" />
                      ) : (
                        <span className="stage-num">{idx + 1}</span>
                      )}
                    </div>
                    <div className="stage-meta">
                      <span className="stage-title">{st.label}</span>
                      <span className="stage-desc">{st.desc}</span>
                    </div>
                    {isCurrent && <span className="stage-active-pulse">Running</span>}
                  </div>
                );
              })}
            </div>

            {jobError && (
              <div className="pres-error-callout">
                <AlertTriangle size={18} />
                <div>
                  <strong>Generation Interrupted</strong>
                  <p>{jobError}</p>
                </div>
              </div>
            )}

            <div className="generating-actions-row">
              <button
                type="button"
                className="btn-danger"
                onClick={handleCancelGeneration}
              >
                Cancel Generation
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={onClose}
                title="Keep running generation in background"
              >
                Run in Background
              </button>
            </div>
          </div>
        )}

        {/* VIEW 3: INTERACTIVE STUDIO & POST-GEN EDITOR */}
        {viewMode === "studio" && deckSpec && (
          <div className="pres-studio-body">
            {/* STUDIO SUB-TOOLBAR */}
            <div className="studio-sub-toolbar">
              <div className="toolbar-left">
                <span className="slide-counter-badge">
                  Slide {activeSlideIndex + 1} of {deckSpec.slides.length}
                </span>

                <div className="theme-quick-dropdown">
                  <Palette size={14} />
                  <select
                    className="select-theme-inline"
                    value={deckSpec.theme?.id || deckSpec.metadata?.theme_id || "executive_dark"}
                    onChange={e => handleSwitchTheme(e.target.value)}
                  >
                    {themes.map(t => (
                      <option key={t.id} value={t.id}>{t.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="toolbar-right">
                <button
                  type="button"
                  className={`btn-ghost-sm ${speakerNotesOpen ? "active" : ""}`}
                  onClick={() => setSpeakerNotesOpen(!speakerNotesOpen)}
                >
                  <FileText size={14} />
                  <span>Speaker Notes</span>
                </button>

                <button
                  type="button"
                  className="btn-ghost-sm"
                  onClick={handleAddSlide}
                  title="Add a new slide to deck"
                >
                  <Plus size={14} />
                  <span>Add Slide</span>
                </button>
              </div>
            </div>

            <div className="studio-main-grid">
              {/* LEFT: SLIDE THUMBNAIL RAIL */}
              <div className="studio-thumbnails-rail">
                <div className="thumbnails-scroll-wrap">
                  {deckSpec.slides.map((s, idx) => {
                    const isActive = idx === activeSlideIndex;
                    return (
                      <div
                        key={s.id || idx}
                        className={`thumbnail-card ${isActive ? "active" : ""}`}
                        onClick={() => setActiveSlideIndex(idx)}
                      >
                        <div className="thumb-header">
                          <span className="thumb-idx">{idx + 1}</span>
                          <span className="thumb-layout-tag">{s.layout?.replace("_", " ")}</span>
                        </div>
                        <div className="thumb-title-preview">{s.title}</div>

                        {/* Thumbnail slide actions */}
                        <div className="thumb-actions" onClick={e => e.stopPropagation()}>
                          <button
                            type="button"
                            className="btn-thumb-action"
                            disabled={idx === 0}
                            onClick={() => handleMoveSlide(idx, -1)}
                            title="Move slide up"
                          >
                            <ArrowUp size={12} />
                          </button>
                          <button
                            type="button"
                            className="btn-thumb-action"
                            disabled={idx === deckSpec.slides.length - 1}
                            onClick={() => handleMoveSlide(idx, 1)}
                            title="Move slide down"
                          >
                            <ArrowDown size={12} />
                          </button>
                          <button
                            type="button"
                            className="btn-thumb-action"
                            onClick={() => handleDuplicateSlide(idx)}
                            title="Duplicate slide"
                          >
                            <Copy size={12} />
                          </button>
                          <button
                            type="button"
                            className="btn-thumb-action danger"
                            onClick={() => handleDeleteSlide(idx)}
                            title="Delete slide"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* CENTER: REVEAL.JS 16:9 PRESENTER */}
              <div className="studio-presenter-center">
                <PresentationRevealDeck
                  slides={deckSpec.slides}
                  theme={currentTheme}
                  activeSlideIndex={activeSlideIndex}
                  onSlideChange={setActiveSlideIndex}
                  isEditable={true}
                  onUpdateSlide={handleUpdateSlide}
                />

                {/* BOTTOM SPEAKER NOTES DRAWER */}
                {speakerNotesOpen && deckSpec.slides[activeSlideIndex] && (
                  <div className="studio-speaker-notes-bar">
                    <div className="notes-bar-header">
                      <div className="notes-header-left">
                        <FileText size={14} />
                        <span>Speaker Notes (Slide {activeSlideIndex + 1})</span>
                      </div>
                      <span className="notes-hint">Exported into PowerPoint presenter view</span>
                    </div>
                    <textarea
                      className="notes-textarea"
                      rows={2}
                      value={deckSpec.slides[activeSlideIndex].speaker_notes || ""}
                      onChange={e => {
                        const updated = { ...deckSpec.slides[activeSlideIndex], speaker_notes: e.target.value };
                        handleUpdateSlide(activeSlideIndex, updated);
                      }}
                      placeholder="Add talking points and executive narrative remarks..."
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* SINGLE SLIDE REGENERATION MODAL */}
        {showRegenModal && (
          <div className="pres-regen-dialog-backdrop">
            <div className="pres-regen-dialog">
              <div className="dialog-header">
                <div className="dialog-title-wrap">
                  <Sparkles size={16} style={{ color: "var(--brand-500, #ff8a62)" }} />
                  <h4>Regenerate Slide {activeSlideIndex + 1}</h4>
                </div>
                <button
                  type="button"
                  className="btn-icon-close"
                  onClick={() => setShowRegenModal(false)}
                >
                  <X size={16} />
                </button>
              </div>

              <div className="dialog-body">
                <p className="dialog-hint">
                  Current Title: <strong>{deckSpec?.slides[activeSlideIndex]?.title}</strong>
                </p>
                <label htmlFor="regen-prompt">AI Guidance / Emphasis Prompt</label>
                <textarea
                  id="regen-prompt"
                  className="form-textarea"
                  rows={3}
                  value={regeneratePrompt}
                  onChange={e => setRegeneratePrompt(e.target.value)}
                  placeholder="e.g. Focus sharply on top 5 store margins and holiday staffing alignment."
                  autoFocus
                />
              </div>

              <div className="dialog-footer">
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => setShowRegenModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn-primary btn-sm"
                  onClick={handleRegenerateSlideSubmit}
                  disabled={isRegeneratingSlide || !regeneratePrompt.trim()}
                >
                  <Sparkles size={14} />
                  <span>{isRegeneratingSlide ? "Regenerating..." : "Apply AI Update"}</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
