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
  RefreshCw,
  Database,
  Link2,
  CheckSquare,
  Square,
  ShieldCheck,
  Info,
  Calendar
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
  exportPresentationPptx,
  previewPresentationScope
} from "../api/client";
import PresentationRevealDeck from "./PresentationRevealDeck.jsx";
import EvidenceInspectionDrawer from "./EvidenceInspectionDrawer.jsx";

const STAGES = [
  { id: "reviewing_coverage", label: "Reviewing Coverage", desc: "Evaluating eligible datasets, boundaries & date ranges" },
  { id: "validating_relationships", label: "Validating Relationships", desc: "Checking cross-sheet link integrity & foreign keys" },
  { id: "collecting_findings", label: "Collecting Findings", desc: "Capturing executive findings & freezing evidence ledger" },
  { id: "synthesizing_outcomes", label: "Synthesizing Outcomes", desc: "Computing macro operational outcomes & benchmarks" },
  { id: "building_slides", label: "Building Slides", desc: "Assembling executive slide deck layouts & visual charts" },
  { id: "verifying_claims", label: "Verifying Claims", desc: "Auditing deterministic claim numbers (±0.1%)" },
  { id: "ready", label: "Ready to Review", desc: "Presentation sealed with cryptographic snapshot hash" }
];

export default function CreatePresentationModal({
  isOpen,
  onClose,
  activeJobId = null,
  initialDeck = null,
  initialScopeType = "workspace",
  onJobUpdate = () => {}
}) {
  const [viewMode, setViewMode] = useState("config"); // "config" | "generating" | "studio"
  const [themes, setThemes] = useState([]);
  const [sheets, setSheets] = useState([]);

  // Scope form state
  const [scopeType, setScopeType] = useState(initialScopeType); // "workspace" | "connected_group" | "custom_sheets" | "single_sheet"
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [customSheetIds, setCustomSheetIds] = useState([]);
  const [scopePreview, setScopePreview] = useState(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  // Core config form state
  const [objective, setObjective] = useState("Executive Leadership Review");
  const [audience, setAudience] = useState("C-Suite & Operations Leadership");
  const [targetLength, setTargetLength] = useState(8);
  const [selectedThemeId, setSelectedThemeId] = useState("executive_dark");
  const [selectedSheetId, setSelectedSheetId] = useState("");
  const [instructions, setInstructions] = useState("");
  const [autoDownload, setAutoDownload] = useState(true);

  // Job progress state
  const [currentJobId, setCurrentJobId] = useState(activeJobId);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobStage, setJobStage] = useState("reviewing_coverage");
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

  // Evidence Inspection Drawer state
  const [isEvidenceDrawerOpen, setIsEvidenceDrawerOpen] = useState(false);
  const [selectedEvidenceSlide, setSelectedEvidenceSlide] = useState(null);

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
          setCustomSheetIds(res.sheets.map(s => String(s.id)));
        }
      })
      .catch(console.error);
  }, [isOpen]);

  // 2. Preflight Scope Preview live auditor
  useEffect(() => {
    if (!isOpen || viewMode !== "config") return;

    let isMounted = true;
    setIsLoadingPreview(true);

    const payload = {
      scope_type: scopeType,
      sheet_id: selectedSheetId ? Number(selectedSheetId) : null,
      sheet_ids: scopeType === "custom_sheets" ? customSheetIds.map(Number) : [],
      group_id: scopeType === "connected_group" && selectedGroupId !== "" ? Number(selectedGroupId) : null
    };

    previewPresentationScope(payload)
      .then(res => {
        if (isMounted) {
          setScopePreview(res);
          if (res.connected_groups && res.connected_groups.length > 0 && selectedGroupId === "") {
            setSelectedGroupId(String(res.connected_groups[0].group_id));
          }
        }
      })
      .catch(err => {
        console.warn("Preflight scope preview error:", err);
      })
      .finally(() => {
        if (isMounted) setIsLoadingPreview(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, viewMode, scopeType, selectedSheetId, customSheetIds, selectedGroupId]);

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
        scope_type: scopeType,
        sheet_id: selectedSheetId ? Number(selectedSheetId) : null,
        sheet_ids: scopeType === "custom_sheets" ? customSheetIds.map(Number) : [],
        group_id: scopeType === "connected_group" && selectedGroupId !== "" ? Number(selectedGroupId) : null,
        instructions
      };
      const res = await startPresentationGeneration(scope);
      setCurrentJobId(res.job_id);
      setJobProgress(5);
      setJobStage("reviewing_coverage");
      setJobStageLabel("Initiating workspace presentation pipeline...");
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
              {/* Left Column: Scope & Core Parameters */}
              <div className="config-col">
                {/* PRESENTATION SCOPE SELECTION */}
                <div className="form-group">
                  <label className="section-label">Presentation Scope</label>
                  <div className="scope-selection-grid">
                    {[
                      {
                        id: "workspace",
                        title: "Executive Workspace Summary",
                        desc: "All eligible datasets & validated relationships",
                        icon: Layers
                      },
                      {
                        id: "connected_group",
                        title: "Selected Connected Group",
                        desc: "Related sheets linked by validated keys",
                        icon: Link2
                      },
                      {
                        id: "custom_sheets",
                        title: "Selected Sheets",
                        desc: "Custom multi-sheet comparison",
                        icon: CheckSquare
                      },
                      {
                        id: "single_sheet",
                        title: "Single Sheet",
                        desc: "Focused deep dive on one dataset",
                        icon: Database
                      }
                    ].map(opt => {
                      const isSelected = scopeType === opt.id;
                      const IconComp = opt.icon;
                      return (
                        <button
                          key={opt.id}
                          type="button"
                          className={`scope-option-card ${isSelected ? "selected" : ""}`}
                          onClick={() => setScopeType(opt.id)}
                        >
                          <div className="scope-card-top">
                            <IconComp size={15} className="scope-icon" />
                            <span className="scope-title">{opt.title}</span>
                            {isSelected && <CheckCircle2 size={14} className="scope-check" />}
                          </div>
                          <span className="scope-desc">{opt.desc}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* SCOPE-DEPENDENT DATASET PICKERS */}
                {scopeType === "single_sheet" && (
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
                )}

                {scopeType === "connected_group" && (
                  <div className="form-group">
                    <label htmlFor="pres-group">Select Connected Group</label>
                    {scopePreview?.connected_groups && scopePreview.connected_groups.length > 0 ? (
                      <select
                        id="pres-group"
                        className="form-select"
                        value={selectedGroupId}
                        onChange={e => setSelectedGroupId(e.target.value)}
                      >
                        {scopePreview.connected_groups.map(g => (
                          <option key={g.group_id} value={g.group_id}>
                            Group {g.group_id + 1}: {g.sheet_names.join(" + ")} ({g.total_rows.toLocaleString()} rows)
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="empty-group-note">
                        <span>No multi-sheet relationships detected. Evaluated within individual group boundaries.</span>
                      </div>
                    )}
                  </div>
                )}

                {scopeType === "custom_sheets" && (
                  <div className="form-group">
                    <label>Choose Sheets to Include ({customSheetIds.length} of {sheets.length} selected)</label>
                    <div className="custom-sheets-checklist">
                      {sheets.map(s => {
                        const isChecked = customSheetIds.includes(String(s.id));
                        return (
                          <label key={s.id} className={`sheet-checkbox-row ${isChecked ? "checked" : ""}`}>
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={e => {
                                if (e.target.checked) {
                                  setCustomSheetIds([...customSheetIds, String(s.id)]);
                                } else {
                                  setCustomSheetIds(customSheetIds.filter(id => id !== String(s.id)));
                                }
                              }}
                            />
                            <span className="sheet-check-name">{s.name}</span>
                            <span className="sheet-check-rows">{s.row_count.toLocaleString()} rows</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* LIVE PREFLIGHT AUDIT CARD */}
                <div className="preflight-summary-card">
                  <div className="preflight-header">
                    <div className="preflight-title">
                      <ShieldCheck size={14} style={{ color: "#8ef0c8" }} />
                      <span>Preflight Scope &amp; Integrity Audit</span>
                    </div>
                    {isLoadingPreview ? (
                      <span className="preflight-status loading">
                        <RotateCw size={11} className="spin-icon" /> Auditing...
                      </span>
                    ) : (
                      <span className="preflight-status ready">Verified Scope</span>
                    )}
                  </div>

                  {scopePreview ? (
                    <div className="preflight-details-stack">
                      <div className="preflight-row">
                        <span className="preflight-lbl">
                          <Database size={12} /> Sources:
                        </span>
                        <span className="preflight-val">
                          {scopePreview.included_sheets?.length || 0} datasets ({(scopePreview.total_records || 0).toLocaleString()} rows)
                        </span>
                      </div>

                      <div className="preflight-row">
                        <span className="preflight-lbl">
                          <Calendar size={12} /> Period:
                        </span>
                        <span className="preflight-val">
                          {scopePreview.reporting_period_summary || "Complete timeline"}
                        </span>
                      </div>

                      {scopePreview.is_partial_year && (
                        <div className="preflight-warning-pill">
                          <AlertTriangle size={12} />
                          <span>Partial Year Disclosure Active (&lt; 330 days in cycle)</span>
                        </div>
                      )}

                      <div className="preflight-row">
                        <span className="preflight-lbl">
                          <Link2 size={12} /> Relationships:
                        </span>
                        <span className="preflight-val">
                          {scopePreview.validated_relationships?.length || 0} validated links ({scopePreview.relationship_coverage_pct || 100}% coverage)
                        </span>
                      </div>

                      {scopePreview.disconnected_boundary_note && (
                        <div className="preflight-boundary-note">
                          <Info size={12} />
                          <span>{scopePreview.disconnected_boundary_note}</span>
                        </div>
                      )}

                      {scopePreview.exclusions && scopePreview.exclusions.length > 0 && (
                        <div className="preflight-exclusions">
                          <span className="exclusions-lbl">Excluded:</span>
                          <span className="exclusions-val">
                            {scopePreview.exclusions.map(ex => `${ex.name} (${ex.reason})`).join("; ")}
                          </span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="preflight-skeleton">Evaluating workspace datasets and relational coverage...</div>
                  )}
                </div>

                <div className="form-group">
                  <label htmlFor="pres-obj">Presentation Objective / Topic</label>
                  <input
                    id="pres-obj"
                    type="text"
                    className="form-input"
                    value={objective}
                    onChange={e => setObjective(e.target.value)}
                    placeholder="e.g. Executive Operations & Performance Review"
                  />
                  <div className="quick-suggestions">
                    <button
                      type="button"
                      className="suggestion-tag"
                      onClick={() => setObjective("Consolidated Executive Operations & Performance Review")}
                    >
                      Consolidated Executive
                    </button>
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

                {deckSpec.metadata?.validation_summary && (
                  <div
                    className={`validation-summary-chip ${deckSpec.metadata.validation_summary.status === "passed" ? "verified" : "flagged"}`}
                    title={`Claim Verification: ${deckSpec.metadata.validation_summary.passed_verification} of ${deckSpec.metadata.validation_summary.total_metrics_checked} verified within ±0.1%`}
                  >
                    <ShieldCheck size={13} />
                    <span>
                      {deckSpec.metadata.validation_summary.status === "passed"
                        ? `Verified (±0.1%) · ${deckSpec.metadata.validation_summary.passed_verification}/${deckSpec.metadata.validation_summary.total_metrics_checked} Passed`
                        : `${deckSpec.metadata.validation_summary.discrepancies_flagged?.length || 1} Discrepancy Flagged`}
                    </span>
                  </div>
                )}

                {deckSpec.metadata?.snapshot_hash && (
                  <span className="snapshot-seal-chip" title={`Cryptographic Snapshot Hash: ${deckSpec.metadata.snapshot_hash}`}>
                    SHA256: {deckSpec.metadata.snapshot_hash.slice(0, 8)}...
                  </span>
                )}
              </div>

              <div className="toolbar-right">
                <button
                  type="button"
                  className={`btn-ghost-sm ${isEvidenceDrawerOpen ? "active" : ""}`}
                  onClick={() => {
                    setSelectedEvidenceSlide(deckSpec.slides[activeSlideIndex]);
                    setIsEvidenceDrawerOpen(true);
                  }}
                  title="Audit calculation methodology, board briefing & reproducible audit ledger"
                >
                  <ShieldCheck size={14} />
                  <span>Audit Evidence</span>
                </button>

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
                  onViewEvidence={(slide) => {
                    setSelectedEvidenceSlide(slide);
                    setIsEvidenceDrawerOpen(true);
                  }}
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

        {/* EVIDENCE INSPECTION DRAWER */}
        <EvidenceInspectionDrawer
          isOpen={isEvidenceDrawerOpen}
          onClose={() => setIsEvidenceDrawerOpen(false)}
          slide={selectedEvidenceSlide || deckSpec?.slides?.[activeSlideIndex]}
          evidenceLedger={deckSpec?.metadata?.evidence_ledger || []}
          snapshotHash={deckSpec?.metadata?.snapshot_hash}
          validationSummary={deckSpec?.metadata?.validation_summary}
          allSlides={deckSpec?.slides || []}
          onSelectSlide={(idx) => {
            setActiveSlideIndex(idx);
            setSelectedEvidenceSlide(deckSpec?.slides?.[idx]);
          }}
        />
      </div>
    </div>
  );
}
