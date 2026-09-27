import React, { useState } from "react";
import {
  Sparkles,
  Layers,
  Palette,
  Image,
  Sliders,
  CheckCircle2,
  ArrowRight,
  ShieldCheck,
  TrendingUp,
  AlertCircle,
  Film,
  Zap,
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
  const [transitionStyle, setTransitionStyle] = useState("dissolve"); // "dissolve" | "sweep" | "none"

  // Dashboard context tokens
  const priorityElement = dashboardData?.quaternary_element;
  const heroSpread = priorityElement?.prominent_number || "—";
  const priorityTitle = priorityElement?.title || "Strategic Priority Disparity";
  const exceptionData = dashboardData?.exception_watch;
  const coverageData = dashboardData?.analysis_coverage;

  const INSPIRATION_PROMPTS = [
    "Q3 Executive Review on Remote Work vs Office Attendance & Operational Productivity",
    "Frontline Turnover Risk, Retention Initiatives & Compensation Impact",
    "Board Strategic Briefing on Headcount Allocation & Departmental Variance",
    "Workforce Attendance Optimization & Shift Overtime Cost Containment",
  ];

  const handleLaunch = () => {
    onGenerateDeck({
      sourceMode,
      customPrompt: sourceMode === "custom_prompt" ? customPrompt : null,
      targetLength: slideCount,
      themeId: selectedThemeId,
      deckStyle: "decision_brief",
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
        <div className="pres-source-tabs">
          <button
            type="button"
            className={`source-tab-btn ${sourceMode === "dashboard_truth" ? "active" : ""}`}
            onClick={() => setSourceMode("dashboard_truth")}
          >
            <Layers size={14} />
            <span>Website & Dashboard Truth (Auto)</span>
          </button>
          <button
            type="button"
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
                <div>
                  <h3 className="pres-step-title">Custom Topic & Talking Points</h3>
                  <p className="pres-step-desc">Enter your presentation topic, notes, or executive brief</p>
                </div>
              </div>
              <div className="pres-prompt-input-wrap">
                <textarea
                  className="pres-prompt-textarea"
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="e.g. Q3 Strategic Attrition Review and Retention Roadmap for Engineering & Support teams..."
                  rows={3}
                />
                <div className="inspiration-chips-row">
                  <span className="chips-label">Inspiration ideas:</span>
                  <div className="chips-scroll">
                    {INSPIRATION_PROMPTS.map((insp, i) => (
                      <button
                        key={i}
                        type="button"
                        className="chip-btn"
                        onClick={() => setCustomPrompt(insp)}
                      >
                        {insp}
                      </button>
                    ))}
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
            <div className="pres-step-options">
              {[
                { count: 5, label: "5 Slides", sub: "Executive Summary" },
                { count: 7, label: "7 Slides (Recommended)", sub: "Boardroom Decision Brief" },
                { count: 10, label: "10 Slides", sub: "Deep-Dive Operating Review" },
              ].map((opt) => (
                <button
                  key={opt.count}
                  type="button"
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
            <div className="pres-theme-grid">
              {[
                { id: "executive_dark", label: "Executive Obsidian", color: "#171412", tag: "Dark Luxury" },
                { id: "corporate_clean", label: "Institutional Ivory", color: "#f8f6f2", tag: "Clean Corporate" },
                { id: "vibrant_accent", label: "High-Impact Monolith", color: "#111827", tag: "Boardroom Brief" },
              ].map((th) => (
                <button
                  key={th.id}
                  type="button"
                  onClick={() => setSelectedThemeId(th.id)}
                  className={`pres-theme-btn ${selectedThemeId === th.id ? "active" : ""}`}
                >
                  <span className="theme-swatch" style={{ backgroundColor: th.color }} />
                  <span className="theme-name">{th.label}</span>
                  <span className="theme-tag">{th.tag}</span>
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
            <div className="pres-bg-row">
              <button
                type="button"
                onClick={() => {
                  setBackgroundMode("solid");
                  setSelectedImage(null);
                }}
                className={`pres-bg-btn ${backgroundMode === "solid" ? "active" : ""}`}
              >
                <Palette size={16} />
                <span>Solid Executive Minimal</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setBackgroundMode("image");
                  setIsImagePickerOpen(true);
                }}
                className={`pres-bg-btn ${backgroundMode === "image" ? "active" : ""}`}
              >
                <Image size={16} />
                <span>{selectedImage ? "Change Image..." : "Browse Free Photos..."}</span>
              </button>
            </div>

            {selectedImage && (
              <div className="pres-selected-image-preview">
                <img src={selectedImage.thumbnail} alt={selectedImage.title} />
                <div className="selected-meta">
                  <span className="title">{selectedImage.title}</span>
                  <span className="author">{selectedImage.creator} (Free License)</span>
                </div>
              </div>
            )}
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
            <div className="pres-transition-pills">
              {[
                { id: "dissolve", label: "Smooth Dissolve (Recommended)" },
                { id: "sweep", label: "Staggered Metric Sweep" },
                { id: "none", label: "Instant Cut" },
              ].map((tr) => (
                <button
                  key={tr.id}
                  type="button"
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
                      <strong>Strategic Priority Spread ({heroSpread})</strong>
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
