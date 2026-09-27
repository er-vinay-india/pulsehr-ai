import React, { useState } from "react";
import {
  Sparkles,
  Layers,
  Palette,
  Image,
  Sliders,
  CheckCircle2,
  Check,
  ArrowRight,
  ShieldCheck,
  TrendingUp,
  AlertCircle,
  Film,
  Zap,
  Users,
  Clock,
  X,
} from "lucide-react";
import SlideImagePickerModal from "./SlideImagePickerModal.jsx";

export default function PromptStudioScreen({
  dashboardData,
  onGenerateDeck,
  isGenerating = false,
  themes = [],
}) {
  const [sourceMode, setSourceMode] = useState("dashboard_truth"); // "dashboard_truth" | "custom_prompt"
  const [customPrompt, setCustomPrompt] = useState("");
  const [slideCount, setSlideCount] = useState(7);
  const [selectedThemeId, setSelectedThemeId] = useState("executive_dark");
  const [backgroundMode, setBackgroundMode] = useState("solid"); // "solid" | "image"
  const [selectedImage, setSelectedImage] = useState(null);
  const [isImagePickerOpen, setIsImagePickerOpen] = useState(false);
  const [transitionStyle, setTransitionStyle] = useState("fade"); // "fade" | "slide" | "scale" | "reveal" | "none"

  const availableThemes = themes && themes.length > 0 ? themes : [
    { id: "executive_dark", name: "Executive Obsidian", bg_color: "#08111F" },
    { id: "bold_signal", name: "Bold Signal", bg_color: "#131418" },
    { id: "electric_studio", name: "Electric Studio", bg_color: "#0a0c10" },
    { id: "clean_light", name: "Clean Modern Light", bg_color: "#ffffff" },
    { id: "corporate_navy", name: "Corporate Navy", bg_color: "#0b1329" },
    { id: "creative_voltage", name: "Creative Voltage", bg_color: "#090914" },
  ];
  const currentThemeObj = availableThemes.find((th) => th.id === selectedThemeId) || availableThemes[0];

  // Priority ordering to guarantee premier themes are shown with executive_dark first
  const THEME_PRIORITY = ["executive_dark", "bold_signal", "clean_light", "corporate_navy", "electric_studio", "creative_voltage"];
  const displayThemes = (availableThemes || []).slice().sort((a, b) => {
    const idxA = THEME_PRIORITY.indexOf(a.id);
    const idxB = THEME_PRIORITY.indexOf(b.id);
    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;
    return 0;
  }).slice(0, 6);

  // Dashboard context tokens
  const priorityElement = dashboardData?.quaternary_element || dashboardData?.primary_element || dashboardData?.priority_element;
  const heroSpread = priorityElement?.formatted_absolute_lift || priorityElement?.prominent_number || priorityElement?.glance?.formatted_value || (priorityElement?.absolute_lift ? String(priorityElement.absolute_lift) : "");
  const priorityTitle = priorityElement?.title || "Strategic Priority & Operational Variance";
  const exceptionData = dashboardData?.exception_element || dashboardData?.exception_watch;
  const forecastData = dashboardData?.outlook_element || dashboardData?.forecast;
  const coverageData = dashboardData?.analysis_coverage;

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

  const handleLaunch = () => {
    onGenerateDeck({
      sourceMode,
      customPrompt: sourceMode === "custom_prompt" ? customPrompt : null,
      targetLength: slideCount,
      themeId: selectedThemeId,
      deckStyle: "standard",
      backgroundMode,
      selectedImageUrl: selectedImage?.url || null,
      transitionStyle,
    });
  };

  return (
    <div className="pres-prompt-studio">
      {/* Studio Header Banner */}
      <div className="pres-prompt-studio__header">
        <div className="pres-prompt-studio__badge">
          <Sparkles size={14} />
          <span>{sourceMode === "dashboard_truth" ? "Zero-Scope AI Studio · Bound to Active Dashboard Truth" : "Executive AI Studio · Custom Topic Synthesis"}</span>
        </div>
        <h1 className="pres-prompt-studio__title">
          Build Boardroom Executive Presentation
        </h1>
        <p className="pres-prompt-studio__subtitle">
          {sourceMode === "dashboard_truth"
            ? "Directly translates active dashboard disparity models, forward forecasts, exception anomalies, and S01–S20 audit evidence into high-impact boardroom slides."
            : "Synthesizes your custom executive briefing prompt into structured, high-impact boardroom slides with empirical rigor."}
        </p>

        {/* Source Mode Toggle */}
        <div className="pres-source-tabs" role="tablist" aria-label="Presentation Source Mode">
          <button
            type="button"
            role="tab"
            aria-selected={sourceMode === "dashboard_truth"}
            className={`source-tab-btn ${sourceMode === "dashboard_truth" ? "active" : ""}`}
            onClick={() => setSourceMode("dashboard_truth")}
          >
            <Layers size={14} />
            <span>Website & Dashboard Truth (Auto)</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={sourceMode === "custom_prompt"}
            className={`source-tab-btn ${sourceMode === "custom_prompt" ? "active" : ""}`}
            onClick={() => setSourceMode("custom_prompt")}
          >
            <Sparkles size={14} />
            <span>Custom Topic & Executive Briefing</span>
          </button>
        </div>
      </div>

      <div className="pres-prompt-studio__grid">
        {/* Left Column: Interactive Generation Pipeline Controls */}
        <div className="pres-prompt-studio__controls-col">
          {/* Custom Prompt Input Section (when custom_prompt mode active) */}
          {sourceMode === "custom_prompt" && (
            <div className="pres-step-card pres-custom-prompt-card">
              <div className="pres-step-card__header">
                <span className="pres-step-badge highlight">✦</span>
                <div style={{ flex: 1 }}>
                  <h3 className="pres-step-title">Custom Topic & Talking Points</h3>
                  <p className="pres-step-desc">Enter your presentation topic, notes, or executive brief</p>
                </div>
                {customPrompt && (
                  <button
                    type="button"
                    className="btn-clear-prompt"
                    onClick={() => setCustomPrompt("")}
                    title="Clear prompt"
                    aria-label="Clear custom briefing prompt"
                  >
                    <X size={13} />
                    <span>Clear</span>
                  </button>
                )}
              </div>
              <div className="pres-prompt-input-wrap">
                <textarea
                  className="pres-prompt-textarea"
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="e.g. Conduct a comprehensive operational review of Store 20 vs Store 33, addressing wage disparity, overtime leakages, and Q4 margin impacts..."
                  aria-label="Custom presentation topic and talking points"
                  rows={3}
                />

                <div className="inspiration-ideas-section">
                  <div className="inspiration-ideas-header">
                    <Sparkles size={13} className="sparkle-icon" />
                    <span className="chips-label">Inspiration ideas (Click to populate briefing):</span>
                  </div>
                  <div className="inspiration-cards-grid" role="group" aria-label="Inspiration briefing prompts">
                    {INSPIRATION_PROMPTS.map((insp) => {
                      const isSelected = customPrompt === insp.title;
                      const Icon = insp.icon;
                      return (
                        <button
                          key={insp.id}
                          type="button"
                          className={`insp-card ${isSelected ? "active" : ""}`}
                          aria-pressed={isSelected}
                          aria-label={`Select inspiration idea: ${insp.title}`}
                          onClick={() => setCustomPrompt(insp.title)}
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
              </div>
            </div>
          )}

          {/* Step 1: Slide Count & Narrative Arc */}
          <div className="pres-step-card">
            <div className="pres-step-card__header">
              <span className="pres-step-badge">1</span>
              <div>
                <h3 className="pres-step-title">Slide Count & Narrative Pacing</h3>
                <p className="pres-step-desc">Select executive narrative depth</p>
              </div>
            </div>
            <div className="pres-step-options" role="radiogroup" aria-label="Slide Count and Narrative Pacing">
              {[
                { count: 5, label: "5 Slides", sub: "Executive Summary" },
                { count: 7, label: "7 Slides (Recommended)", sub: "Boardroom Decision Brief" },
                { count: 10, label: "10 Slides", sub: "Deep-Dive Operating Review" },
              ].map((opt) => (
                <button
                  key={opt.count}
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

          {/* Step 2: Theme & Visual Palette */}
          <div className="pres-step-card">
            <div className="pres-step-card__header">
              <span className="pres-step-badge">2</span>
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
                  <span className="theme-swatch" style={{ backgroundColor: th.bg_color || th.color }} />
                  <span className="theme-name">{th.name || th.label}</span>
                  <span className="theme-tag">{th.id.replace(/_/g, " ")}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Step 3: Background Atmosphere & Free Imagery */}
          <div className="pres-step-card">
            <div className="pres-step-card__header">
              <span className="pres-step-badge">3</span>
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
                      : "Enterprise workplace photography with automatic dark scrim guaranteeing AAA white text legibility."}
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

          {/* Step 4: Animation & Transitions */}
          <div className="pres-step-card">
            <div className="pres-step-card__header">
              <span className="pres-step-badge">4</span>
              <div>
                <h3 className="pres-step-title">Animation & Reveal Pacing</h3>
                <p className="pres-step-desc">Subtle transitions designed for executive focus</p>
              </div>
            </div>
            <div className="pres-transition-pills" role="radiogroup" aria-label="Animation and Reveal Pacing">
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
        </div>

        {/* Right Column: Dashboard Data Truth & Slide Blueprint Preview */}
        <div className="pres-prompt-studio__preview-col">
          <div className="pres-blueprint-card">
            <div className="pres-blueprint-header">
              <div className="blueprint-title-row">
                <Layers size={18} />
                <h4>{sourceMode === "custom_prompt" ? "Custom Briefing Blueprint" : "Dashboard Truth Extraction"}</h4>
              </div>
              <span className="verified-seal">
                <ShieldCheck size={13} /> {sourceMode === "custom_prompt" ? "AI Narrative Synthesis" : "Empirical Binding"}
              </span>
            </div>

            <p className="blueprint-summary">
              {sourceMode === "custom_prompt"
                ? "Slides will be intelligently generated from your executive prompt with analytical rigor and structured layouts:"
                : "Slides are automatically populated with active metrics directly from the Adaptive Dashboard:"}
            </p>

            <div className="pres-slide-outline-list">
              {sourceMode === "custom_prompt" ? (
                <>
                  <div className="outline-item">
                    <span className="item-num">1</span>
                    <div className="item-body">
                      <strong>Executive Mandate & Overview</strong>
                      <span>{customPrompt ? (customPrompt.length > 50 ? customPrompt.slice(0, 48) + "..." : customPrompt) : "Custom Executive Topic Title"}</span>
                    </div>
                    <span className="item-badge">Title</span>
                  </div>

                  <div className="outline-item">
                    <span className="item-num">2</span>
                    <div className="item-body">
                      <strong>Strategic Context & Problem Statement</strong>
                      <span>Root cause evaluation and baseline challenge breakdown</span>
                    </div>
                    <span className="item-badge highlight">Problem Frame</span>
                  </div>

                  <div className="outline-item">
                    <span className="item-num">3</span>
                    <div className="item-body">
                      <strong>Performance Drivers & Resource Allocation</strong>
                      <span>Frontline capacity load & operational concentration</span>
                    </div>
                    <span className="item-badge">Drivers</span>
                  </div>

                  <div className="outline-item">
                    <span className="item-num">4</span>
                    <div className="item-body">
                      <strong>Cross-Unit Benchmarking & Variance</strong>
                      <span>Standardized comparison across business units</span>
                    </div>
                    <span className="item-badge">Benchmark</span>
                  </div>

                  <div className="outline-item">
                    <span className="item-num">5</span>
                    <div className="item-body">
                      <strong>Governance & Risk Guardrails</strong>
                      <span>Simpson&apos;s Paradox protection & defensible decision rules</span>
                    </div>
                    <span className="item-badge">Audit Seal</span>
                  </div>

                  {slideCount >= 6 && (
                    <div className="outline-item">
                      <span className="item-num">6</span>
                      <div className="item-body">
                        <strong>Forward Projections & Operational Horizons</strong>
                        <span>Predictive forecast model with confidence intervals</span>
                      </div>
                      <span className="item-badge">Forecast</span>
                    </div>
                  )}

                  {slideCount >= 7 && (
                    <div className="outline-item">
                      <span className="item-num">{slideCount}</span>
                      <div className="item-body">
                        <strong>Strategic Action Plan & Accountability</strong>
                        <span>60-day phased roadmap & executive ownership matrix</span>
                      </div>
                      <span className="item-badge">Roadmap</span>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div className="outline-item">
                    <span className="item-num">1</span>
                    <div className="item-body">
                      <strong>Executive Mandate & Overview</strong>
                      <span>{priorityTitle}</span>
                    </div>
                    <span className="item-badge">Title</span>
                  </div>

                  <div className="outline-item">
                    <span className="item-num">2</span>
                    <div className="item-body">
                      <strong>Strategic Priority Spread{heroSpread && heroSpread !== "—" ? ` (${heroSpread})` : ""}</strong>
                      <span>Donut / Bounded Bar chart translated directly from dashboard</span>
                    </div>
                    <span className="item-badge highlight">Donut Embed</span>
                  </div>

                  <div className="outline-item">
                    <span className="item-num">3</span>
                    <div className="item-body">
                      <strong>Unit Distribution Breakdown</strong>
                      <span>Comparative spread across qualified operational peer units</span>
                    </div>
                    <span className="item-badge">Breakdown</span>
                  </div>

                  {exceptionData && (
                    <div className="outline-item">
                      <span className="item-num">4</span>
                      <div className="item-body">
                        <strong>Exception Watch Anomaly</strong>
                        <span>{exceptionData.unusual_period || "Outlier window"} · {exceptionData.observed_value_formatted}</span>
                      </div>
                      <span className="item-badge alert">Alert Callout</span>
                    </div>
                  )}

                  <div className="outline-item">
                    <span className="item-num">5</span>
                    <div className="item-body">
                      <strong>Defensible Forward Outlook</strong>
                      <span>3-month forward projection with confidence intervals</span>
                    </div>
                    <span className="item-badge">Forecast</span>
                  </div>

                  <div className="outline-item">
                    <span className="item-num">6</span>
                    <div className="item-body">
                      <strong>HR Strategy Coverage & Intelligence Audit</strong>
                      <span>S01–S20 evaluation · Simpson&apos;s Paradox guardrails active</span>
                    </div>
                    <span className="item-badge">Audit Seal</span>
                  </div>

                  <div className="outline-item">
                    <span className="item-num">7</span>
                    <div className="item-body">
                      <strong>Action Plan & Owner Accountability</strong>
                      <span>Operations Lead · 14-day review cycle & target mitigations</span>
                    </div>
                    <span className="item-badge">Roadmap</span>
                  </div>
                </>
              )}
            </div>

            {/* Launch Studio Action */}
            <div className="pres-launch-box">
              <button
                type="button"
                onClick={handleLaunch}
                disabled={isGenerating}
                className="btn-launch-presentation"
              >
                {isGenerating ? (
                  <>
                    <Zap size={18} className="spin-icon" />
                    <span>Materializing Boardroom Presentation...</span>
                  </>
                ) : (
                  <>
                    <span>Build Slides with HRIDAY Studio</span>
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
              <p className="launch-subtext">
                Slides will be loaded into the 16:9 interactive studio with full HRIDAY curation, HRIDAY heart voiceover, and editable PPTX export.
              </p>
            </div>
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
