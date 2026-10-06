import React, { useState, useMemo, useCallback, useEffect, useRef } from "react";
import {
  Sparkles,
  Layers,
  Palette,
  Image,
  CheckCircle2,
  Check,
  ArrowRight,
  ArrowLeft,
  TrendingUp,
  AlertCircle,
  Film,
  Zap,
  Users,
  Clock,
  X,
  Database,
  Target,
  FileText,
  Sliders,
} from "lucide-react";
import { SLIDE_THEMES } from "../../theme/slideTokens.js";
import SlideImagePickerModal from "./SlideImagePickerModal.jsx";
import Select from "../common/Select.jsx";

const DEFAULT_THEMES = Object.values(SLIDE_THEMES);

const THEME_PRIORITY = [
  "amber_brush",
  "executive_dark",
  "bold_signal",
  "clean_light",
  "corporate_navy",
  "electric_studio",
  "creative_voltage",
];

const INSPIRATION_PROMPTS = [
  {
    id: "remote_work",
    tag: "Productivity & Hybrid",
    icon: TrendingUp,
    title: "Q3 Executive Review on Remote Work vs Office Attendance & Operational Productivity",
    desc: "Evaluates attendance benchmarks, individual productivity variance, and remote policy impacts.",
  },
  {
    id: "turnover_risk",
    tag: "Retention & Talent",
    icon: Users,
    title: "Frontline Turnover Risk, Retention Initiatives & Compensation Impact",
    desc: "Analyzes frontline attrition trends, competitive pay bands, and targeted retention programs.",
  },
  {
    id: "headcount_alloc",
    tag: "Strategy & Budget",
    icon: Layers,
    title: "Board Strategic Briefing on Headcount Allocation & Departmental Variance",
    desc: "Boardroom decision review on capacity planning, headcount allocation, and organizational drift.",
  },
  {
    id: "overtime_cost",
    tag: "Operations & Cost",
    icon: Clock,
    title: "Workforce Attendance Optimization & Shift Overtime Cost Containment",
    desc: "Quantifies shift leakages, overtime run-rates, and schedule optimization cost-reduction opportunities.",
  },
];

const AUDIENCE_SUGGESTIONS = [
  "Executive leadership",
  "Board of Directors",
  "CFO & Audit Committee",
  "People Operations Leaders",
];

export default function PromptStudioScreen({
  dashboardData,
  onGenerateDeck,
  isGenerating = false,
  themes = [],
  sheets = [],
  selectedSheetId,
  onSelectSheet,
  latestDeck = null,
  onOpenLatestDeck = () => {},
  onDeleteLatestDeck = () => {},
  detectedPersona = null,
  relevantPersonas = [],
  error,
}) {
  // 3-Step Guided Form: 1 = Source & Topic, 2 = Narrative Depth, 3 = Theme & Polish
  const [currentStep, setCurrentStep] = useState(1);
  const stepContainerRef = useRef(null);
  const previousStepRef = useRef(currentStep);

  useEffect(() => {
    if (previousStepRef.current === currentStep) return;
    previousStepRef.current = currentStep;
    const frame = requestAnimationFrame(() => {
      const heading = stepContainerRef.current?.querySelector("h2");
      heading?.focus({ preventScroll: true });
      heading?.scrollIntoView({ block: "start", behavior: "auto" });
    });
    return () => cancelAnimationFrame(frame);
  }, [currentStep]);

  const [pathDrafts, setPathDrafts] = useState({
    dashboard_truth: { audience: "Executive leadership", instructions: "", sourceScope: "single_sheet" },
    custom_prompt: { audience: "Executive leadership", instructions: "", sourceScope: "single_sheet" },
  });
  const [brief, setBrief] = useState("");
  const [decisionRequested, setDecisionRequested] = useState("");
  const [mainTakeaway, setMainTakeaway] = useState("");
  const [presentationTimeMinutes, setPresentationTimeMinutes] = useState(15);
  const [deliverable, setDeliverable] = useState("pptx");
  const [animation, setAnimation] = useState("none");
  const [sourceMode, setSourceMode] = useState("dashboard_truth"); // "dashboard_truth" | "custom_prompt"
  const [customPrompt, setCustomPrompt] = useState("");
  const { audience, instructions, sourceScope } = pathDrafts[sourceMode];

  const updatePathDraft = (field, value) =>
    setPathDrafts((drafts) => ({
      ...drafts,
      [sourceMode]: { ...drafts[sourceMode], [field]: value },
    }));

  const setAudience = (value) => updatePathDraft("audience", value);
  const setInstructions = (value) => updatePathDraft("instructions", value);
  const setSourceScope = (value) => updatePathDraft("sourceScope", value);

  const [slideCount, setSlideCount] = useState(null); // null = Adaptive auto
  const [selectedThemeId, setSelectedThemeId] = useState("amber_brush");
  const [backgroundMode, setBackgroundMode] = useState("solid"); // "solid" | "image"
  const [selectedImage, setSelectedImage] = useState(null);
  const [isImagePickerOpen, setIsImagePickerOpen] = useState(false);
  const [transitionStyle, setTransitionStyle] = useState("fade"); // "fade" | "slide" | "scale" | "reveal" | "none"

  const availableThemes = useMemo(
    () => (themes && themes.length > 0 ? themes : DEFAULT_THEMES),
    [themes]
  );

  const displayThemes = useMemo(() => {
    return availableThemes
      .slice()
      .sort((a, b) => {
        const idxA = THEME_PRIORITY.indexOf(a.id);
        const idxB = THEME_PRIORITY.indexOf(b.id);
        if (idxA !== -1 && idxB !== -1) return idxA - idxB;
        if (idxA !== -1) return -1;
        if (idxB !== -1) return 1;
        return 0;
      })
      .slice(0, 7);
  }, [availableThemes]);

  const currentThemeObj = useMemo(
    () => availableThemes.find((th) => th.id === selectedThemeId) || availableThemes[0],
    [availableThemes, selectedThemeId]
  );

  const handleLaunch = useCallback(() => {
    onGenerateDeck({
      sourceMode,
      audience,
      objective: sourceMode === "dashboard_truth" ? brief : "",
      decisionRequested,
      mainTakeaway,
      presentationTimeMinutes: Number(presentationTimeMinutes) || 15,
      deliverable,
      instructions,
      scopeType: sourceScope,
      customPrompt: sourceMode === "custom_prompt" ? customPrompt : null,
      targetLength: slideCount,
      themeId: selectedThemeId,
      deckStyle: "standard",
      backgroundMode: currentThemeObj?.background_asset ? "solid" : backgroundMode,
      selectedImageUrl: currentThemeObj?.background_asset ? null : selectedImage?.url || null,
      transitionStyle,
      animation,
      scrimOpacity: selectedImage?.scrimOpacity ?? 70,
    });
  }, [
    currentThemeObj,
    onGenerateDeck,
    sourceMode,
    audience,
    brief,
    decisionRequested,
    mainTakeaway,
    presentationTimeMinutes,
    deliverable,
    instructions,
    sourceScope,
    customPrompt,
    slideCount,
    selectedThemeId,
    backgroundMode,
    selectedImage,
    transitionStyle,
    animation,
  ]);

  const canProceedStep1 = useMemo(() => {
    if (sourceMode === "dashboard_truth") {
      return Boolean(selectedSheetId);
    }
    return Boolean(customPrompt.trim());
  }, [sourceMode, selectedSheetId, customPrompt]);

  return (
    <div className="pres-prompt-studio pres-minimal-studio">
      {/* Studio Header & Stepper */}
      <div className="pres-studio-hero">
        {/* 3-Step Guided Stepper Bar */}
        <nav className="pres-stepper-nav" aria-label="Presentation creation steps">
          <button
            type="button"
            className={`pres-step-tab ${currentStep === 1 ? "active" : ""} ${currentStep > 1 ? "completed" : ""}`}
            onClick={() => setCurrentStep(1)}
            aria-current={currentStep === 1 ? "step" : undefined}
          >
            <span className="step-num">{currentStep > 1 ? <Check size={13} /> : "1"}</span>
            <div className="step-meta">
              <span className="step-label">
                <Database size={13} className="step-label-icon" aria-hidden="true" />
                <span>Source & Focus</span>
              </span>
              <span className="step-desc">
                {sourceMode === "dashboard_truth" ? "Active Data Truth" : "Custom Briefing"}
              </span>
            </div>
          </button>

          <span className="step-divider" aria-hidden="true" />

          <button
            type="button"
            className={`pres-step-tab ${currentStep === 2 ? "active" : ""} ${currentStep > 2 ? "completed" : ""}`}
            onClick={() => setCurrentStep(2)}
            aria-current={currentStep === 2 ? "step" : undefined}
          >
            <span className="step-num">{currentStep > 2 ? <Check size={13} /> : "2"}</span>
            <div className="step-meta">
              <span className="step-label">
                <Sliders size={13} className="step-label-icon" aria-hidden="true" />
                <span>Narrative Depth</span>
              </span>
              <span className="step-desc">
                {slideCount === null ? "Adaptive" : `${slideCount} Slides`}
              </span>
            </div>
          </button>

          <span className="step-divider" aria-hidden="true" />

          <button
            type="button"
            className={`pres-step-tab ${currentStep === 3 ? "active" : ""}`}
            onClick={() => setCurrentStep(3)}
            aria-current={currentStep === 3 ? "step" : undefined}
          >
            <span className="step-num">3</span>
            <div className="step-meta">
              <span className="step-label">
                <Palette size={13} className="step-label-icon" aria-hidden="true" />
                <span>Theme & Polish</span>
              </span>
              <span className="step-desc">{currentThemeObj.name}</span>
            </div>
          </button>
        </nav>
      </div>

      {error && (
        <div className="pres-studio-error-banner" role="alert">
          <AlertCircle size={16} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {/* STEP CONTAINER */}
      <div className="pres-step-container" ref={stepContainerRef}>
        {/* =========================================================================
            STEP 1: SOURCE & TOPIC
            ========================================================================= */}
        {currentStep === 1 && (
          <section className="pres-minimal-card" aria-labelledby="step1-heading">
            <div className="step-card-header">
              <span className="step-badge-indicator">Step 1 of 3</span>
              <h2 id="step1-heading" className="step-card-title" tabIndex={-1}>
                What would you like to present?
              </h2>
              <p className="step-card-subtitle">
                Select whether to build directly from your verified dataset or supply custom talking points.
              </p>
            </div>

            {/* Last Generated Presentation Quick Action Card */}
            {latestDeck && (
              <div
                className="pres-latest-deck-banner"
                style={{
                  background: "var(--color-bg-surface)",
                  border: "1px solid var(--color-border-strong)",
                  borderRadius: "12px",
                  padding: "16px 20px",
                  marginBottom: "24px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  boxShadow: "var(--shadow-sm)"
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                  <div
                    style={{
                      background: "var(--color-bg-soft-teal)",
                      borderRadius: "10px",
                      padding: "10px",
                      color: "var(--color-brand-accent)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center"
                    }}
                  >
                    <FileText size={22} />
                  </div>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                      <span style={{ fontSize: "11px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--color-brand-accent)" }}>
                        Last Generated Presentation
                      </span>
                      <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>•</span>
                      <span style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>
                        {latestDeck.slides?.length || 0} Slides
                      </span>
                    </div>
                    <h4 style={{ margin: 0, fontSize: "15px", fontWeight: "600", color: "var(--color-text-primary)" }}>
                      {latestDeck.metadata?.title || latestDeck.title || "Executive Presentation"}
                    </h4>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <button
                    type="button"
                    className="btn-open-latest-deck"
                    onClick={() => onOpenLatestDeck && onOpenLatestDeck(latestDeck)}
                    style={{
                      background: "var(--btn-primary-bg)",
                      color: "var(--btn-primary-fg)",
                      border: "none",
                      borderRadius: "8px",
                      padding: "8px 16px",
                      fontSize: "13px",
                      fontWeight: "600",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px"
                    }}
                  >
                    <span>Open & Edit Last PPT</span>
                    <ArrowRight size={14} />
                  </button>
                  <button
                    type="button"
                    className="btn-delete-latest-deck"
                    onClick={() => onDeleteLatestDeck && onDeleteLatestDeck(latestDeck.id || latestDeck.deck_id)}
                    style={{
                      background: "var(--color-bg-soft-error)",
                      color: "var(--color-error)",
                      border: "1px solid var(--color-border-strong)",
                      borderRadius: "8px",
                      padding: "8px 14px",
                      fontSize: "13px",
                      fontWeight: "500",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "6px"
                    }}
                    title="Delete previous presentation to start fresh"
                  >
                    <span>Delete & Create New</span>
                  </button>
                </div>
              </div>
            )}

            {/* Source Mode Chooser (Large Spacious Cards) */}
            <div className="pres-source-mode-grid" role="radiogroup" aria-label="Select presentation source">
              <button
                type="button"
                role="radio"
                aria-checked={sourceMode === "dashboard_truth"}
                className={`source-mode-card ${sourceMode === "dashboard_truth" ? "active" : ""}`}
                onClick={() => setSourceMode("dashboard_truth")}
              >
                <div className="mode-card-header">
                  <div className="mode-icon-wrap database">
                    <Database size={20} aria-hidden="true" />
                  </div>
                  {sourceMode === "dashboard_truth" && (
                    <span className="mode-active-pill">
                      <Check size={12} /> Active
                    </span>
                  )}
                </div>
                <h3 className="mode-card-title">Active Dataset Truth</h3>
                <p className="mode-card-desc">
                  Directly translates verified metrics, disparity models, and audit evidence into executive slides.
                </p>
              </button>

              <button
                type="button"
                role="radio"
                aria-checked={sourceMode === "custom_prompt"}
                className={`source-mode-card ${sourceMode === "custom_prompt" ? "active" : ""}`}
                onClick={() => setSourceMode("custom_prompt")}
              >
                <div className="mode-card-header">
                  <div className="mode-icon-wrap sparkles">
                    <Sparkles size={20} aria-hidden="true" />
                  </div>
                  {sourceMode === "custom_prompt" && (
                    <span className="mode-active-pill">
                      <Check size={12} /> Active
                    </span>
                  )}
                </div>
                <h3 className="mode-card-title">Custom Objective & Memo</h3>
                <p className="mode-card-desc">
                  Present on a custom operational objective, executive memo, or briefing grounded in data.
                </p>
              </button>
            </div>

            {/* Mode-Specific Fields */}
            {sourceMode === "dashboard_truth" && (
              <div className="pres-form-section">
                <div className="form-row-grid">
                  <div className="pres-form-group">
                    <label htmlFor="pres-sheet-select" className="pres-field-label">
                      <Database size={14} className="field-icon" aria-hidden="true" />
                      <span>Source Dataset</span>
                    </label>
                    <Select
                      id="pres-sheet-select"
                      className="pres-field-control"
                      value={selectedSheetId || ""}
                      onChange={(e) => onSelectSheet(e.target.value)}
                      placeholder={sheets.length ? "Select source dataset…" : "No uploaded datasets"}
                      options={
                        !sheets.length
                          ? [{ value: "", label: "No uploaded datasets" }]
                          : sheets.map((sheet) => ({
                              value: sheet.id,
                              label: `${sheet.name || sheet.sheet_name || sheet.title || `Sheet ${sheet.id}`} ${sheet.dataset_name ? `— ${sheet.dataset_name}` : `(ID ${sheet.id})`}`
                            }))
                      }
                      fullWidth
                    />
                    <span className="pres-field-hint">
                      Extracts baseline facts and disparity models directly from this sheet.
                    </span>
                    {detectedPersona && (
                      <div
                        className="pres-detected-persona-badge"
                        style={{
                          background: "var(--color-bg-soft-teal)",
                          border: "1px solid var(--color-border-strong)",
                          borderRadius: "8px",
                          padding: "8px 12px",
                          marginTop: "8px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between"
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ width: "7px", height: "7px", borderRadius: "50%", backgroundColor: "var(--color-brand-accent)" }} />
                          <span style={{ fontSize: "12px", color: "var(--color-brand-accent)", fontWeight: "600" }}>
                            {detectedPersona.role_title}
                          </span>
                        </div>
                        <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
                          Standard: {detectedPersona.standard_report_name}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="pres-form-group">
                    <label htmlFor="pres-scope-select" className="pres-field-label">
                      <Layers size={14} className="field-icon" aria-hidden="true" />
                      <span>Evidence Coverage</span>
                    </label>
                    <Select
                      id="pres-scope-select"
                      className="pres-field-control"
                      value={sourceScope}
                      onChange={(e) => setSourceScope(e.target.value)}
                      options={[
                        { value: "single_sheet", label: "Active sheet only" },
                        { value: "workspace", label: "All eligible workspace sheets (Cross-synthesis)" }
                      ]}
                      fullWidth
                    />
                    <span className="pres-field-hint">
                      Defines whether multi-sheet cross-reconciliation synthesis is enabled.
                    </span>
                  </div>
                </div>

                <div className="pres-form-group">
                  <label htmlFor="pres-brief-input" className="pres-field-label">
                    <Target size={14} className="field-icon" aria-hidden="true" />
                    <span>Presentation Objective (Optional)</span>
                  </label>
                  <input
                    id="pres-brief-input"
                    type="text"
                    className="pres-field-control"
                    value={brief}
                    onChange={(e) => setBrief(e.target.value)}
                    placeholder={detectedPersona?.standard_report_name || "e.g. Executive review of departmental attendance disparities and Q3 headcount risks"}
                  />
                </div>
              </div>
            )}

            {sourceMode === "custom_prompt" && (
              <div className="pres-form-section">
                <div className="pres-form-group">
                  <div className="label-with-action">
                    <label htmlFor="pres-custom-textarea" className="pres-field-label">
                      <FileText size={14} className="field-icon" aria-hidden="true" />
                      <span>Presentation Topic & Key Briefing Notes</span>
                    </label>
                    {customPrompt && (
                      <button
                        type="button"
                        className="btn-text-clear"
                        onClick={() => setCustomPrompt("")}
                        aria-label="Clear custom text"
                      >
                        <X size={12} /> Clear
                      </button>
                    )}
                  </div>
                  <textarea
                    id="pres-custom-textarea"
                    className="pres-field-control pres-textarea-lg"
                    rows={4}
                    value={customPrompt}
                    onChange={(e) => setCustomPrompt(e.target.value)}
                    placeholder="Enter your topic, key talking points, or executive mandate (e.g. 'Conduct a comprehensive review of Operations vs Engineering attrition, addressing compensation disparities and Q4 overtime leakages')..."
                  />
                </div>

                {/* Inspiration Prompt Chips */}
                <div className="inspiration-container">
                  <span className="insp-label">Quick Inspiration Topics:</span>
                  <div className="insp-pills-row" role="group" aria-label="Inspiration prompts">
                    {INSPIRATION_PROMPTS.map((insp) => {
                      const fullPrompt = `${insp.title}. ${insp.desc}`;
                      const isSelected = customPrompt === fullPrompt || customPrompt === insp.title;
                      return (
                        <button
                          key={insp.id}
                          type="button"
                          className={`insp-chip ${isSelected ? "selected" : ""}`}
                          onClick={() => setCustomPrompt(isSelected ? "" : fullPrompt)}
                          aria-pressed={isSelected}
                        >
                          <span className="chip-tag">{insp.tag}:</span>
                          <span className="chip-title">{insp.title.substring(0, 48)}…</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* Target Audience (Common across both modes) */}
            <div className="pres-form-section audience-section">
              <div className="pres-form-group">
                <label htmlFor="pres-audience-input" className="pres-field-label">
                  <Users size={14} className="field-icon" aria-hidden="true" />
                  <span>Target Audience</span>
                </label>
                <input
                  id="pres-audience-input"
                  type="text"
                  className="pres-field-control"
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  placeholder="e.g. Executive leadership, Board of Directors"
                />
                <div className="quick-audience-pills">
                  {AUDIENCE_SUGGESTIONS.map((sug) => (
                    <button
                      key={sug}
                      type="button"
                      className={`audience-pill ${audience === sug ? "active" : ""}`}
                      onClick={() => setAudience(sug)}
                    >
                      {sug}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Step 1 Actions */}
            <div className="step-action-bar">
              <button
                type="button"
                className="btn-quick-launch"
                onClick={handleLaunch}
                disabled={isGenerating || !canProceedStep1}
                title="Generate presentation immediately using optimal defaults"
              >
                <Zap size={15} aria-hidden="true" />
                <span>Instant Launch with Defaults</span>
              </button>

              <button
                type="button"
                className="btn-step-primary"
                onClick={() => setCurrentStep(2)}
                disabled={!canProceedStep1}
              >
                <span>Continue to Narrative Depth</span>
                <ArrowRight size={16} aria-hidden="true" />
              </button>
            </div>
          </section>
        )}

        {/* =========================================================================
            STEP 2: NARRATIVE DEPTH & SLIDE COUNT
            ========================================================================= */}
        {currentStep === 2 && (
          <section className="pres-minimal-card" aria-labelledby="step2-heading">
            <div className="step-card-header">
              <span className="step-badge-indicator">Step 2 of 3</span>
              <h2 id="step2-heading" className="step-card-title" tabIndex={-1}>
                Choose narrative pacing and depth
              </h2>
              <p className="step-card-subtitle">
                Select how deep the boardroom story should go, or calibrate dynamically based on data signals.
              </p>
            </div>

            {/* Narrative Depth Cards */}
            <div className="narrative-cards-grid" role="radiogroup" aria-label="Select slide count and narrative pacing">
              {[
                {
                  count: null,
                  badge: "Recommended",
                  title: "Adaptive (Auto-Calibrated)",
                  slides: "8–11 Slides",
                  time: "~15 mins",
                  desc: "Dynamically sizes the presentation based on observed disparities, baseline facts, and multi-sheet linkages.",
                },
                {
                  count: 5,
                  badge: "Concise",
                  title: "Executive Summary",
                  slides: "5 Slides",
                  time: "~5 mins",
                  desc: "Focused executive briefing: core baseline, primary strength, prominent headwind, and immediate next steps.",
                },
                {
                  count: 7,
                  badge: "Strategic",
                  title: "Boardroom Decision Brief",
                  slides: "7 Slides",
                  time: "~12 mins",
                  desc: "Balanced strategic review: scope baseline, operational strengths, headwinds, disparity breakdown, and governance.",
                },
                {
                  count: 10,
                  badge: "Comprehensive",
                  title: "Deep-Dive Operating Review",
                  slides: "10 Slides",
                  time: "~25 mins",
                  desc: "Exhaustive operational analysis including cross-dimensional linkages, evidence ledgers, and audit trail limits.",
                },
              ].map((opt) => {
                const isSelected = slideCount === opt.count;
                return (
                  <button
                    key={String(opt.count)}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    className={`narrative-card ${isSelected ? "selected" : ""}`}
                    onClick={() => setSlideCount(opt.count)}
                  >
                    <div className="narrative-card-top">
                      <span className={`narrative-badge ${opt.badge.toLowerCase()}`}>{opt.badge}</span>
                      {isSelected && (
                        <span className="narrative-check">
                          <Check size={13} /> Selected
                        </span>
                      )}
                    </div>
                    <h3 className="narrative-title">{opt.title}</h3>
                    <div className="narrative-meta">
                      <span className="meta-item"><Layers size={13} /> {opt.slides}</span>
                      <span className="meta-item"><Clock size={13} /> {opt.time}</span>
                    </div>
                    <p className="narrative-desc">{opt.desc}</p>
                  </button>
                );
              })}
            </div>

            {/* Executive Brief Specifications */}
            <div className="pres-form-section brief-spec-section">
              <div className="pres-form-group">
                <label htmlFor="pres-main-takeaway-input" className="pres-field-label">
                  <FileText size={14} className="field-icon" aria-hidden="true" />
                  <span>Main Takeaway</span>
                </label>
                <input
                  id="pres-main-takeaway-input"
                  type="text"
                  className="pres-field-control"
                  value={mainTakeaway}
                  onChange={(e) => setMainTakeaway(e.target.value)}
                  placeholder="e.g. Voluntary attrition concentrated in Engineering; compensation adjustments needed"
                />
              </div>

              <div className="pres-form-group" style={{ marginTop: "12px" }}>
                <label htmlFor="pres-decision-requested-input" className="pres-field-label">
                  <Sliders size={14} className="field-icon" aria-hidden="true" />
                  <span>Decision or Action Requested</span>
                </label>
                <input
                  id="pres-decision-requested-input"
                  type="text"
                  className="pres-field-control"
                  value={decisionRequested}
                  onChange={(e) => setDecisionRequested(e.target.value)}
                  placeholder="e.g. Approve targeted $2.4M retention equity program for high-impact roles"
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginTop: "12px" }}>
                <div className="pres-form-group">
                  <label htmlFor="pres-time-budget-input" className="pres-field-label">
                    <Clock size={14} className="field-icon" aria-hidden="true" />
                    <span>Presentation Time Budget (Minutes)</span>
                  </label>
                  <input
                    id="pres-time-budget-input"
                    type="number"
                    min="3"
                    max="60"
                    className="pres-field-control"
                    value={presentationTimeMinutes}
                    onChange={(e) => setPresentationTimeMinutes(Number(e.target.value) || 15)}
                  />
                </div>

                <div className="pres-form-group">
                  <label htmlFor="pres-deliverable-select" className="pres-field-label">
                    <Database size={14} className="field-icon" aria-hidden="true" />
                    <span>Deliverable Format</span>
                  </label>
                  <Select
                    id="pres-deliverable-select"
                    className="pres-field-control"
                    value={deliverable}
                    onChange={(e) => setDeliverable(e.target.value)}
                    options={[
                      { value: "pptx", label: "PowerPoint (.pptx)" },
                      { value: "pdf", label: "Document PDF (.pdf)" },
                      { value: "both", label: "Both (.pptx + .pdf)" }
                    ]}
                    fullWidth
                  />
                </div>
              </div>
            </div>

            {/* Additional Guidance & Instructions */}
            <div className="pres-form-section guidance-section">
              <div className="pres-form-group">
                <label htmlFor="pres-guidance-input" className="pres-field-label">
                  <FileText size={14} className="field-icon" aria-hidden="true" />
                  <span>Additional Guidance & Constraints (Optional)</span>
                </label>
                <textarea
                  id="pres-guidance-input"
                  className="pres-field-control"
                  rows={2}
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder="Topics to emphasize, specific KPIs to highlight, exclusions, or executive committee reporting boundaries..."
                />
                <span className="pres-field-hint">
                  Constraints are passed directly to the presentation execution orchestrator.
                </span>
              </div>
            </div>

            {/* Step 2 Actions */}
            <div className="step-action-bar">
              <button
                type="button"
                className="btn-step-back"
                onClick={() => setCurrentStep(1)}
              >
                <ArrowLeft size={16} aria-hidden="true" />
                <span>Back to Source</span>
              </button>

              <div className="step-action-right">
                <button
                  type="button"
                  className="btn-quick-launch"
                  onClick={handleLaunch}
                  disabled={isGenerating}
                  title="Generate presentation immediately using current settings"
                >
                  <Zap size={15} aria-hidden="true" />
                  <span>Launch Now</span>
                </button>

                <button
                  type="button"
                  className="btn-step-primary"
                  onClick={() => setCurrentStep(3)}
                >
                  <span>Continue to Theme & Style</span>
                  <ArrowRight size={16} aria-hidden="true" />
                </button>
              </div>
            </div>
          </section>
        )}

        {/* =========================================================================
            STEP 3: THEME & VISUAL POLISH
            ========================================================================= */}
        {currentStep === 3 && (
          <section className="pres-minimal-card" aria-labelledby="step3-heading">
            <div className="step-card-header">
              <span className="step-badge-indicator">Step 3 of 3</span>
              <h2 id="step3-heading" className="step-card-title" tabIndex={-1}>
                Visual palette and presentation style
              </h2>
              <p className="step-card-subtitle">
                Calibrated for executive screen sharing, 4K boardroom projectors, and high-readability delivery.
              </p>
            </div>

            {/* Theme Grid */}
            <div className="themes-section">
              <h3 className="section-sub-title">Select Color Palette</h3>
              <div className="pres-theme-grid" role="radiogroup" aria-label="Theme and Visual Palette">
                {displayThemes.map((th) => {
                  const isSelected = selectedThemeId === th.id;
                  return (
                    <button
                      key={th.id}
                      type="button"
                      role="radio"
                      aria-checked={isSelected}
                      aria-label={`${th.name || th.label} visual theme`}
                      onClick={() => setSelectedThemeId(th.id)}
                      className={`pres-theme-btn ${isSelected ? "active" : ""}`}
                    >
                      <span
                        className="theme-swatch"
                        style={{ backgroundColor: th.bg_color || th.color || "#0F1B2D", ...(th.background_asset ? { backgroundImage: `url(/api/presentations/theme-assets/${th.id}/background)`, backgroundSize: "100% 100%" } : {}) }}
                      >
                        <span
                          className="swatch-card"
                          style={{
                            backgroundColor: th.card_bg || "rgba(255,255,255,0.1)",
                            borderColor: th.card_border || "rgba(255,255,255,0.2)",
                          }}
                        >
                          <span
                            className="swatch-accent-dot"
                            style={{ backgroundColor: th.accent_color || th.brand_color || "#38bdf8" }}
                          />
                          <span
                            className="swatch-accent-bar"
                            style={{ backgroundColor: th.brand_color || th.accent_color || "#60a5fa" }}
                          />
                        </span>
                      </span>
                      <div className="theme-text-wrap">
                        <span className="theme-name">{th.name || th.label}</span>
                        <span className="theme-tag">{th.id.replace(/_/g, " ")}</span>
                      </div>
                      {isSelected && (
                        <span className="theme-selected-badge">
                          <Check size={12} />
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Presentation Delivery Fine-Tuning */}
            <div className="polish-settings-grid">
              {/* Background Atmosphere */}
              <div className="polish-block">
                <h4 className="polish-block-title">Background Atmosphere</h4>
                <div className="polish-options-row" role="radiogroup" aria-label="Background Atmosphere">
                  <button
                    type="button"
                    role="radio"
                    aria-checked={Boolean(currentThemeObj?.background_asset) || backgroundMode === "solid"}
                    className={`polish-pill ${currentThemeObj?.background_asset || backgroundMode === "solid" ? "active" : ""}`}
                    onClick={() => {
                      setBackgroundMode("solid");
                      setSelectedImage(null);
                    }}
                  >
                    <Palette size={14} />
                    <span>{currentThemeObj?.background_asset ? "Amber Brush Background" : "Clean Minimal Solid"}</span>
                  </button>

                  <button
                    type="button"
                    role="radio"
                    disabled={Boolean(currentThemeObj?.background_asset)}
                    title={currentThemeObj?.background_asset ? "Amber Brush includes its own office-photo background" : undefined}
                    aria-checked={!currentThemeObj?.background_asset && backgroundMode === "image"}
                    className={`polish-pill ${!currentThemeObj?.background_asset && backgroundMode === "image" ? "active" : ""}`}
                    onClick={() => {
                      setBackgroundMode("image");
                      if (!selectedImage) setIsImagePickerOpen(true);
                    }}
                  >
                    <Image size={14} />
                    <span>
                      {selectedImage ? `Photo: ${selectedImage.title?.substring(0, 18)}…` : "Workplace Photography"}
                    </span>
                  </button>
                </div>
                {backgroundMode === "image" && !currentThemeObj?.background_asset && (
                  <button
                    type="button"
                    className="btn-browse-photos"
                    onClick={() => setIsImagePickerOpen(true)}
                  >
                    <Image size={13} />
                    <span>{selectedImage ? "Change Photography" : "Browse Free Photos..."}</span>
                  </button>
                )}
              </div>

              {/* Slide Transitions */}
              <div className="polish-block">
                <h4 className="polish-block-title">Slide Transition</h4>
                <div className="polish-options-row" role="radiogroup" aria-label="Slide Transition Effect">
                  {[
                    { id: "fade", label: "Smooth Fade" },
                    { id: "slide", label: "Slide" },
                    { id: "scale", label: "Scale Zoom" },
                    { id: "none", label: "Instant" },
                  ].map((tr) => (
                    <button
                      key={tr.id}
                      type="button"
                      role="radio"
                      aria-checked={transitionStyle === tr.id}
                      onClick={() => setTransitionStyle(tr.id)}
                      className={`polish-pill ${transitionStyle === tr.id ? "active" : ""}`}
                    >
                      <Film size={13} />
                      <span>{tr.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Step 3 Actions (Final Launch Bar) */}
            <div className="step-action-bar final-bar">
              <button
                type="button"
                className="btn-step-back"
                onClick={() => setCurrentStep(2)}
              >
                <ArrowLeft size={16} aria-hidden="true" />
                <span>Back to Narrative</span>
              </button>

              <button
                type="button"
                onClick={handleLaunch}
                disabled={isGenerating || !canProceedStep1}
                className="btn-launch-final"
              >
                {isGenerating ? (
                  <>
                    <Zap size={18} className="spin-icon" />
                    <span>Synthesizing slides with HRIDAY...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={18} />
                    <span>Build Presentation in Interactive Studio</span>
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </div>
          </section>
        )}
      </div>

      {/* Image Picker Modal */}
      <SlideImagePickerModal
        isOpen={isImagePickerOpen}
        onClose={() => setIsImagePickerOpen(false)}
        onSelectImage={(imgData) => {
          setSelectedImage(imgData);
          setBackgroundMode("image");
        }}
      />
    </div>
  );
}
