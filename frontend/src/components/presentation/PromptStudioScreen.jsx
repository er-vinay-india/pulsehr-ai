import React, { useState, useMemo, useCallback } from "react";
import {
  Sparkles,
  Layers,
  Palette,
  Image,
  Sliders,
  CheckCircle2,
  Check,
  ArrowRight,
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
} from "lucide-react";
import SlideImagePickerModal from "./SlideImagePickerModal.jsx";

const DEFAULT_THEMES = [
  { id: "executive_dark", name: "Executive Obsidian", bg_color: "#08111F", card_bg: "#0F1B2D", card_border: "#26384D", accent_color: "#5EEAD4", brand_color: "#60A5FA" },
  { id: "bold_signal", name: "Bold Signal", bg_color: "#131418", card_bg: "#1c1e24", card_border: "#2c2f38", accent_color: "#ff8a65", brand_color: "#ff5722" },
  { id: "electric_studio", name: "Electric Studio", bg_color: "#0a0c10", card_bg: "#141820", card_border: "#232b3a", accent_color: "#4cc9f0", brand_color: "#4361ee" },
  { id: "clean_light", name: "Clean Modern Light", bg_color: "#ffffff", card_bg: "#f8fafc", card_border: "#e2e8f0", accent_color: "#0284c7", brand_color: "#2563eb" },
  { id: "corporate_navy", name: "Corporate Navy", bg_color: "#0b1329", card_bg: "#131f42", card_border: "#23335e", accent_color: "#38bdf8", brand_color: "#2563eb" },
  { id: "creative_voltage", name: "Creative Voltage", bg_color: "#090914", card_bg: "#111126", card_border: "#21214a", accent_color: "#0055ff", brand_color: "#00f0ff" },
];

const THEME_PRIORITY = [
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

export default function PromptStudioScreen({
  dashboardData,
  onGenerateDeck,
  isGenerating = false,
  themes = [],
  sheets = [],
  selectedSheetId,
  onSelectSheet,
  error,
}) {
  const [pathDrafts, setPathDrafts] = useState({
    dashboard_truth: { audience: "Executive leadership", instructions: "", sourceScope: "single_sheet" },
    custom_prompt: { audience: "Executive leadership", instructions: "", sourceScope: "single_sheet" },
  });
  const [brief, setBrief] = useState("");
  const [animation, setAnimation] = useState("none");
  const [sourceMode, setSourceMode] = useState("dashboard_truth"); // "dashboard_truth" | "custom_prompt"
  const [customPrompt, setCustomPrompt] = useState("");
  const { audience, instructions, sourceScope } = pathDrafts[sourceMode];
  const updatePathDraft = (field, value) => setPathDrafts((drafts) => ({
    ...drafts, [sourceMode]: { ...drafts[sourceMode], [field]: value },
  }));
  const setAudience = (value) => updatePathDraft("audience", value);
  const setInstructions = (value) => updatePathDraft("instructions", value);
  const setSourceScope = (value) => updatePathDraft("sourceScope", value);
  const [slideCount, setSlideCount] = useState(null);
  const [selectedThemeId, setSelectedThemeId] = useState("executive_dark");
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
      .slice(0, 6);
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
      instructions,
      scopeType: sourceScope,
      customPrompt: sourceMode === "custom_prompt" ? customPrompt : null,
      targetLength: slideCount,
      themeId: selectedThemeId,
      deckStyle: "standard",
      backgroundMode,
      selectedImageUrl: selectedImage?.url || null,
      transitionStyle,
      animation,
      scrimOpacity: selectedImage?.scrimOpacity ?? 70,
    });
  }, [
    onGenerateDeck,
    sourceMode,
    audience,
    brief,
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

  return (
    <div className="pres-prompt-studio pres-setup-disclosure">
      {/* Studio Header Banner */}
      <div className="pres-prompt-studio__header">
        <h1 className="pres-prompt-studio__title">Create a presentation</h1>

      </div>

      {error && (
        <div className="pres-studio-error-banner" role="alert">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="pres-prompt-studio__grid">
        <div className="pres-prompt-studio__controls-col">
          <h2 className="pres-step-title">How would you like to start?</h2>
        {/* Source Mode Toggle */}
        <div className="pres-source-tabs" role="group" aria-label="Presentation Source Mode">
          <button
            type="button"
                        aria-pressed={sourceMode === "dashboard_truth"}
            className={`source-tab-btn ${sourceMode === "dashboard_truth" ? "active" : ""}`}
            onClick={() => setSourceMode("dashboard_truth")}
          >
            <Layers size={14} />
            <span>Use Existing Data</span>
          </button>
          <button
            type="button"
                        aria-pressed={sourceMode === "custom_prompt"}
            className={`source-tab-btn ${sourceMode === "custom_prompt" ? "active" : ""}`}
            onClick={() => setSourceMode("custom_prompt")}
          >
            <Sparkles size={14} />
            <span>Provide Context</span>
          </button>
        </div>
          <div className="pres-step-card pres-scope-card" key={`fields-${sourceMode}`}>
            <p className="pres-step-desc">
              {sourceMode === "dashboard_truth"
                ? "Use an already uploaded dataset, workspace or dashboard."
                : "Describe your topic, talking points or executive brief."}
            </p>
            {sourceMode === "custom_prompt" && (
              <div className="pres-form-group">
                <label htmlFor="pres-context" className="pres-form-label">What do you want to present?</label>
                <textarea id="pres-context" className="pres-prompt-textarea" rows={3}
                  value={customPrompt} onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="Enter your topic, talking points, or executive brief" />
                {customPrompt && (
                  <button type="button" className="btn-clear-prompt" onClick={() => setCustomPrompt("")}
                    aria-label="Clear custom briefing prompt"><X size={13} /> Clear</button>
                )}
                <p className="pres-field-hint">
                  {selectedSheetId
                    ? "Uses the currently selected sheet as supporting evidence."
                    : "Select an uploaded sheet in Use Existing Data before generating a briefing."}
                </p>
              </div>
            )}
            <div className="pres-scope-form-grid">
              {sourceMode === "dashboard_truth" && (<>
              <div className="pres-form-group">
                <label htmlFor="pres-sheet" className="pres-form-label">
                  <Database size={13} />
                  <span>Source Dataset</span>
                </label>
                <select
                  id="pres-sheet"
                  className="pres-select"
                  value={selectedSheetId || ""}
                  onChange={(e) => onSelectSheet(e.target.value)}
                >
                  {!sheets.length && <option value="">No uploaded datasets</option>}
                  {sheets.map((sheet) => (
                    <option key={sheet.id} value={sheet.id}>
                      {sheet.name || sheet.sheet_name || sheet.title || `Sheet ${sheet.id}`}{" "}
                      {sheet.dataset_name ? `— ${sheet.dataset_name}` : `(ID ${sheet.id})`}
                    </option>
                  ))}
                </select>
              </div>

              <div className="pres-form-group">
                <label htmlFor="pres-scope" className="pres-form-label">
                  <Layers size={13} />
                  <span>Evidence Coverage</span>
                </label>
                <select
                  id="pres-scope"
                  className="pres-select"
                  value={sourceScope}
                  onChange={(e) => setSourceScope(e.target.value)}
                >
                  <option value="single_sheet">Active sheet only</option>
                  <option value="workspace">All eligible workspace sheets</option>
                </select>
              </div>

              </>)}
              <div className="pres-form-group">
                <label htmlFor="pres-audience" className="pres-form-label">
                  <Users size={13} />
                  <span>Target Audience</span>
                </label>
                <input
                  id="pres-audience"
                  type="text"
                  className="pres-input"
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  placeholder="e.g. Executive leadership, Board of Directors"
                />
              </div>



            </div>
          </div>

          <details key={`advanced-${sourceMode}`} className="pres-setup-advanced pres-step-card">
            <summary className="pres-form-label">Advanced options</summary>
            <div className="pres-scope-card">
              <div className="pres-scope-form-grid">
            {sourceMode === "custom_prompt" && (
              <div className="pres-form-group">
                <label htmlFor="pres-scope" className="pres-form-label">
                  <Layers size={13} />
                  <span>Evidence Coverage</span>
                </label>
                <select
                  id="pres-scope"
                  className="pres-select"
                  value={sourceScope}
                  onChange={(e) => setSourceScope(e.target.value)}
                >
                  <option value="single_sheet">Active sheet only</option>
                  <option value="workspace">All eligible workspace sheets</option>
                </select>
              </div>

            )}
            {sourceMode === "dashboard_truth" && (
              <div className="pres-form-group">
                <label htmlFor="pres-brief" className="pres-form-label">Presentation objective (optional)</label>
                <input id="pres-brief" className="pres-input" value={brief}
                  onChange={(e) => setBrief(e.target.value)}
                  placeholder="Executive summary of the selected dataset" />
              </div>
            )}
              <div className="pres-form-group pres-form-group--full">
                <label htmlFor="pres-instructions" className="pres-form-label">
                  <FileText size={13} />
                  <span>Additional Guidance & Constraints (Optional)</span>
                </label>
                <textarea
                  id="pres-instructions"
                  className="pres-textarea"
                  rows={2}
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder="Topics to emphasize, exclusions, specific KPIs, or board reporting requirements..."
                />
              </div>
            </div>
            </div>
            {sourceMode === "custom_prompt" && (
                <div className="inspiration-ideas-section">
                  <div className="inspiration-ideas-header">
                    <Sparkles size={13} className="sparkle-icon" />
                    <span className="chips-label">Inspiration ideas (Click to populate briefing):</span>
                  </div>
                  <div className="inspiration-cards-grid" role="group" aria-label="Inspiration briefing prompts">
                    {INSPIRATION_PROMPTS.map((insp) => {
                      const fullPrompt = `${insp.title}. ${insp.desc}`;
                      const isSelected = customPrompt === fullPrompt || customPrompt === insp.title;
                      const Icon = insp.icon;
                      return (
                        <button
                          key={insp.id}
                          type="button"
                          className={`insp-card ${isSelected ? "active" : ""}`}
                          aria-pressed={isSelected}
                          aria-label={`Select inspiration idea: ${insp.title}`}
                          onClick={() => {
                            if (isSelected) {
                              setCustomPrompt("");
                            } else {
                              setCustomPrompt(fullPrompt);
                            }
                          }}
                        >
                          <div className="insp-card-top">
                            <span className="insp-tag-badge">
                              <Icon size={12} />
                              <span>{insp.tag}</span>
                            </span>
                            {isSelected && (
                              <span className="insp-active-pill">
                                <Check size={11} /> Selected
                              </span>
                            )}
                          </div>
                          <h4 className="insp-card-title">{insp.title}</h4>
                          <p className="insp-card-desc">{insp.desc}</p>
                        </button>
                      );
                    })}
                  </div>
                </div>
            )}
          {/* Step: Slide Count & Narrative Arc */}
          <div className="pres-step-card">
            <div className="pres-step-card__header">
              <div>
                <h3 className="pres-step-title">Slide Count & Narrative Pacing</h3>
                <p className="pres-step-desc">Select executive narrative depth or let HRIDAY decide dynamically</p>
              </div>
            </div>
            <div className="pres-step-options pres-step-options--4" role="radiogroup" aria-label="Slide Count and Narrative Pacing">
              {[
                { count: null, label: "Adaptive (Auto)", sub: "Evidence-Driven Depth" },
                { count: 5, label: "5 Slides", sub: "Executive Summary" },
                { count: 7, label: "7 Slides (Recommended)", sub: "Boardroom Decision Brief" },
                { count: 10, label: "10 Slides", sub: "Deep-Dive Operating Review" },
              ].map((opt) => (
                <button
                  key={String(opt.count)}
                  type="button"
                  role="radio"
                  aria-checked={slideCount === opt.count}
                  onClick={() => setSlideCount(opt.count)}
                  className={`pres-option-btn ${slideCount === opt.count ? "active" : ""}`}
                >
                  <span className="opt-label">{opt.label}</span>
                  <span className="opt-sub">{opt.sub}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Step: Theme & Visual Palette */}
          <div className="pres-step-card">
            <div className="pres-step-card__header">
              <div>
                <h3 className="pres-step-title">Theme & Visual Palette</h3>
                <p className="pres-step-desc">Optimized for boardroom screen sharing & projectors</p>
              </div>
            </div>
            <div className="pres-theme-grid" role="radiogroup" aria-label="Theme and Visual Palette">
              {displayThemes.map((th) => (
                <button
                  key={th.id}
                  type="button"
                  role="radio"
                  aria-checked={selectedThemeId === th.id}
                  aria-label={`${th.name || th.label} visual theme`}
                  onClick={() => setSelectedThemeId(th.id)}
                  className={`pres-theme-btn ${selectedThemeId === th.id ? "active" : ""}`}
                >
                  <span
                    className="theme-swatch"
                    style={{ backgroundColor: th.bg_color || th.color || "#0F1B2D" }}
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
                  <span className="theme-name">{th.name || th.label}</span>
                  <span className="theme-tag">{th.id.replace(/_/g, " ")}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Step: Background Atmosphere & Free Imagery */}
          <div className="pres-step-card">
            <div className="pres-step-card__header">
              <div>
                <h3 className="pres-step-title">Background & Royalty-Free Imagery</h3>
                <p className="pres-step-desc">Commercial-use photography with automatic contrast scrim</p>
              </div>
            </div>
            <div className="pres-bg-cards-grid" role="radiogroup" aria-label="Background Atmosphere & Royalty-Free Imagery">
              {/* Option 1: Solid Executive Minimal */}
              <div
                role="radio"
                tabIndex={0}
                aria-checked={backgroundMode === "solid"}
                aria-label={`Solid Executive Minimal with ${currentThemeObj.name} solid background`}
                onClick={() => {
                  setBackgroundMode("solid");
                  setSelectedImage(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setBackgroundMode("solid");
                    setSelectedImage(null);
                  }
                }}
                className={`pres-bg-card ${backgroundMode === "solid" ? "active" : ""}`}
              >
                <div className="pres-bg-card__top">
                  <div className="pres-bg-card__header-left">
                    <Palette size={16} className="card-icon" />
                    <span className="card-title">Solid Executive Minimal</span>
                  </div>
                  {backgroundMode === "solid" && (
                    <span className="pres-bg-active-badge">
                      <Check size={12} /> Active
                    </span>
                  )}
                </div>

                {/* 16:9 Canvas Simulation of Solid Theme */}
                <div
                  className="pres-bg-canvas-preview"
                  style={{
                    backgroundColor: currentThemeObj.bg_color || "#08111F",
                  }}
                  aria-hidden="true"
                >
                  <div className="canvas-mockup-slide">
                    <div
                      className="mockup-title-bar"
                      style={{
                        backgroundColor: currentThemeObj.primary_text || "#F8FAFC",
                      }}
                    />
                    <div
                      className="mockup-line"
                      style={{
                        backgroundColor: currentThemeObj.accent_color || "#5EEAD4",
                      }}
                    />
                    <div
                      className="mockup-line short"
                      style={{
                        backgroundColor: currentThemeObj.secondary_text || "#94A3B8",
                      }}
                    />
                    <div className="mockup-footer-badge">
                      <span>{currentThemeObj.name} · Solid Palette</span>
                    </div>
                  </div>
                </div>

                <div className="pres-bg-card__details">
                  <p className="card-desc">
                    Distraction-free solid background optimized for boardroom screens, dense tables, and financial charts.
                  </p>
                  <div className="card-meta-row">
                    <span
                      className="meta-color-swatch"
                      style={{ backgroundColor: currentThemeObj.bg_color || "#08111F" }}
                    />
                    <span className="meta-color-code">{currentThemeObj.bg_color || "#08111F"}</span>
                    <span className="meta-tag">Zero Image Noise</span>
                  </div>
                </div>
              </div>

              {/* Option 2: Commercial Royalty-Free Imagery */}
              <div
                role="radio"
                tabIndex={0}
                aria-checked={backgroundMode === "image"}
                aria-label={`Commercial Royalty-Free Photography with automatic contrast scrim${selectedImage ? `: ${selectedImage.title}` : ""}`}
                onClick={() => {
                  setBackgroundMode("image");
                  if (!selectedImage) {
                    setIsImagePickerOpen(true);
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setBackgroundMode("image");
                    if (!selectedImage) {
                      setIsImagePickerOpen(true);
                    }
                  }
                }}
                className={`pres-bg-card ${backgroundMode === "image" ? "active" : ""}`}
              >
                <div className="pres-bg-card__top">
                  <div className="pres-bg-card__header-left">
                    <Image size={16} className="card-icon" />
                    <span className="card-title">Commercial-Use Photography</span>
                  </div>
                  {backgroundMode === "image" && (
                    <span className="pres-bg-active-badge">
                      <Check size={12} /> Active
                    </span>
                  )}
                </div>

                {/* 16:9 Canvas Simulation of Scrim Photo */}
                <div
                  className="pres-bg-canvas-preview photo-canvas"
                  style={{
                    backgroundImage: `url(${selectedImage ? selectedImage.thumbnail : "https://images.unsplash.com/photo-1497366216548-37526070297c?w=600&auto=format&fit=crop&q=80"})`,
                  }}
                  aria-hidden="true"
                >
                  <div
                    className="canvas-scrim-overlay"
                    style={{
                      backgroundColor: `rgba(11, 31, 58, ${(selectedImage?.scrimOpacity || 70) / 100})`,
                    }}
                  >
                    <div className="canvas-mockup-slide">
                      <div className="mockup-title-bar light" />
                      <div className="mockup-line light" />
                      <div className="mockup-line short light" />
                      <div className="mockup-footer-badge scrim">
                        <span>{selectedImage ? `${selectedImage.scrimOpacity || 70}% Contrast Scrim` : "70% Contrast Scrim"}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="pres-bg-card__details">
                  <p className="card-desc">
                    {selectedImage
                      ? `"${selectedImage.title}" by ${selectedImage.creator}. Automatic contrast scrim applied.`
                      : "Enterprise workplace photography with automatic dark scrim guaranteeing readable contrast for slide text."}
                  </p>
                  <div className="card-actions-row">
                    <button
                      type="button"
                      className="btn-select-photo"
                      onClick={(e) => {
                        e.stopPropagation();
                        setBackgroundMode("image");
                        setIsImagePickerOpen(true);
                      }}
                    >
                      <Image size={13} />
                      <span>{selectedImage ? "Change Photography..." : "Browse Free Photos..."}</span>
                    </button>
                    {selectedImage && (
                      <span className="meta-tag photo-source">Unsplash Free License</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Step: Animation & Transitions */}
          <div className="pres-step-card">
            <div className="pres-step-card__header">
              <div>
                <h3 className="pres-step-title">Animation & Transitions</h3>
                <p className="pres-step-desc">Subtle slide transitions and element reveal pacing designed for executive focus</p>
              </div>
            </div>

            <div className="pres-animation-settings-row">
              <div className="pres-animation-section">
                <span className="pres-section-subheading">Slide Transition Effect</span>
                <div className="pres-transition-pills" role="radiogroup" aria-label="Slide Transition Effect">
                  {[
                    { id: "fade", label: "Smooth Fade (Recommended)" },
                    { id: "slide", label: "Directional Slide" },
                    { id: "scale", label: "Scale Zoom" },
                    { id: "reveal", label: "Executive Reveal" },
                    { id: "none", label: "Instant Cut" },
                  ].map((tr) => (
                    <button
                      key={tr.id}
                      type="button"
                      role="radio"
                      aria-checked={transitionStyle === tr.id}
                      onClick={() => setTransitionStyle(tr.id)}
                      className={`transition-pill ${transitionStyle === tr.id ? "active" : ""}`}
                    >
                      <Film size={13} />
                      <span>{tr.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="pres-animation-section">
                <span className="pres-section-subheading">Element Reveal Pacing</span>
                <div className="pres-reveal-pills" role="radiogroup" aria-label="Element Reveal Pacing">
                  {[
                    { id: "none", label: "Instant (All Elements Visible)" },
                    { id: "fade", label: "Progressive Fade-In" },
                  ].map((anim) => (
                    <button
                      key={anim.id}
                      type="button"
                      role="radio"
                      aria-checked={animation === anim.id}
                      onClick={() => setAnimation(anim.id)}
                      className={`transition-pill ${animation === anim.id ? "active" : ""}`}
                    >
                      <Zap size={13} />
                      <span>{anim.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          </details>

          {/* Launch Studio Action */}
          <div className="pres-launch-box">
            <button
              type="button"
              onClick={handleLaunch}
              disabled={isGenerating || !selectedSheetId || (sourceMode === "custom_prompt" && !customPrompt.trim())}
              className="btn-launch-presentation"
            >
              {isGenerating ? (
                <>
                  <Zap size={18} className="spin-icon" />
                  <span>Loading source preview...</span>
                </>
              ) : (
                <>
                  <span>Generate Presentation</span>
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </div>
        </div>
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
