import React, { useState } from "react";
import {
  Palette,
  Clock,
  FileText,
  Plus,
  ArrowUp,
  ArrowDown,
  Copy,
  Trash2,
  Sparkles,
  Download,
  Printer,
  Maximize2,
  Minimize2,
  Image,
  ChevronLeft,
  ChevronRight,
  Check,
  RotateCcw,
  Zap,
  Film,
  Sliders,
} from "lucide-react";
import PresentationRevealDeck from "../PresentationRevealDeck.jsx";
import { exportStandaloneHtmlPresentation } from "../../utils/standaloneHtmlExporter";
import SlideImagePickerModal from "./SlideImagePickerModal.jsx";
import AcousticOrbPresenter from "./AcousticOrbPresenter.jsx";
import AnimatedAcousticOrb from "./AnimatedAcousticOrb.jsx";

const SUGGESTION_PROMPTS = [
  "Highlight disparity spread & cost risk",
  "Condense to 2 high-impact takeaways",
  "Make tone more decisive for Board",
  "Rephrase for CFO & Executive Committee",
  "Emphasize Simpson's Paradox guardrail",
];

export default function DeckStudioView({
  deckSpec,
  activeSlideIndex,
  setActiveSlideIndex,
  themes = [],
  onSwitchTheme,
  currentTheme,
  isEvidenceDrawerOpen,
  onOpenEvidence,
  speakerNotesOpen,
  setSpeakerNotesOpen,
  onAddSlide,
  onMoveSlide,
  onDuplicateSlide,
  onDeleteSlide,
  onUpdateSlide,
  onExportPptx,
  selectedThemeId,
  onSetSlideImage,
  onSetTransition,
  onOpenRegenerate,
  onRefineSlide,
  isBusy = false,
  onApplyImage
}) {
  const [isImagePickerOpen, setIsImagePickerOpen] = useState(false);
  const [isPresenterMode, setIsPresenterMode] = useState(false);
  const [curatePrompt, setCuratePrompt] = useState("");
  const [isCurating, setIsCurating] = useState(false);
  const [curationError, setCurationError] = useState("");
  const [previousSlideSnapshot, setPreviousSlideSnapshot] = useState(null);
  const [showApprovalBanner, setShowApprovalBanner] = useState(false);

  const evidenceLocked = false; // Factual boundary: Editorial content freely editable; metrics tracked with USER_OVERRIDE
  const currentSlide = deckSpec.slides[activeSlideIndex] || deckSpec.slides[0];

  // Handle Copilot Slide Curation
  const handleApplyCopilotCuration = async (promptText) => {
    const prompt = (promptText || curatePrompt).trim();
    if (!prompt || !currentSlide || isBusy || isCurating) return;

    setIsCurating(true);
    // Snapshot current state for Revert capability
    setPreviousSlideSnapshot(JSON.parse(JSON.stringify(currentSlide)));

    try {
      setCurationError("");
      const result = await onRefineSlide(prompt);
      if (!result) { setCurationError("HRIDAY could not refine this slide. Your content is unchanged. Please try again."); return; }
      setShowApprovalBanner(true);
      setCuratePrompt("");
    } catch (err) {
      setCurationError(err.message || "HRIDAY could not refine this slide. Please try again.");
    } finally {
      setIsCurating(false);
    }
  };

  const handleAcceptChanges = () => {
    setShowApprovalBanner(false);
    setPreviousSlideSnapshot(null);
  };

  const handleRevertChanges = () => {
    if (previousSlideSnapshot) {
      onUpdateSlide(activeSlideIndex, previousSlideSnapshot);
      setShowApprovalBanner(false);
      setPreviousSlideSnapshot(null);
    }
  };

  const handleSelectImage = (selection) => (onSetSlideImage || onApplyImage)?.(selection);

  React.useEffect(() => {
    document.dispatchEvent(new CustomEvent("presentation-presenter", { detail: isPresenterMode }));
    return () => document.dispatchEvent(new CustomEvent("presentation-presenter", { detail: false }));
  }, [isPresenterMode]);
  React.useEffect(() => {
    setShowApprovalBanner(false);
    setPreviousSlideSnapshot(null);
  }, [currentSlide?.id]);

  const handlePrintPdf = () => {
    exportStandaloneHtmlPresentation(deckSpec, selectedThemeId, true);
  };

  return (
    <div className={`pres-studio-body ${isPresenterMode ? "theater-presenter-mode" : ""}`}>
      {/* STUDIO SUB-TOOLBAR */}
      <fieldset className="studio-sub-toolbar pres-editor-fieldset" disabled={isBusy}>
        <div className="toolbar-left">
          <span className="slide-counter-badge">
            Slide {activeSlideIndex + 1} of {deckSpec.slides.length}
          </span>

          <div className="symbolic-btn-wrap">
            <div className="theme-quick-dropdown">
              <Palette size={14} />
              <select
                className="select-theme-inline"
                value={deckSpec.theme?.id || deckSpec.metadata?.theme_id || "executive_dark"}
                onChange={(e) => onSwitchTheme(e.target.value)}
                aria-label="Switch Theme"
              >
                {themes.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            <span className="symbolic-tooltip">Visual Theme Palette</span>
          </div>

          <div className="symbolic-btn-wrap">
            <div className="theme-quick-dropdown">
              <Film size={14} />
              <select
                className="select-theme-inline"
                value={currentSlide.transition || deckSpec.metadata?.transition || "none"}
                onChange={(e) => {
                  const val = e.target.value;
                  onUpdateSlide(activeSlideIndex, { ...currentSlide, transition: val });
                }}
                aria-label="Slide Transition"
              >
                <option value="none">Transition: None</option>
                <option value="fade">Transition: Fade</option>
                <option value="slide">Transition: Slide</option>
                <option value="scale">Transition: Scale</option>
                <option value="reveal">Transition: Reveal</option>
              </select>
            </div>
            <span className="symbolic-tooltip">Slide Transition Effect</span>
          </div>

          <div className="symbolic-btn-wrap">
            <div className="theme-quick-dropdown">
              <Sliders size={14} />
              <select
                className="select-theme-inline"
                value={currentSlide.layout || "chart_narrative"}
                onChange={(e) => {
                  const val = e.target.value;
                  onUpdateSlide(activeSlideIndex, { ...currentSlide, layout: val });
                }}
                aria-label="Slide Layout"
              >
                <option value="chart_narrative">Layout: Chart & Insights</option>
                <option value="full_chart_takeaway">Layout: Hero Chart</option>
                <option value="two_charts">Layout: Dual Charts</option>
                <option value="comparison_split">Layout: Strategic Split</option>
                <option value="title_hero">Layout: Executive Hero</option>
                <option value="image_story">Layout: Visual Image Story</option>
                <option value="table_detail">Layout: Evidence Table</option>
                <option value="title_cover">Layout: Title Cover</option>
              </select>
            </div>
            <span className="symbolic-tooltip">Slide Layout Variant</span>
          </div>
        </div>

        <div className="toolbar-right">
          {/* Executive AI Orb Launcher */}
          <div className="symbolic-btn-wrap">
            <button
              type="button"
              className={`symbolic-action-btn btn-present-orb ${isPresenterMode ? "active" : ""}`}
              onClick={() => setIsPresenterMode(!isPresenterMode)}
              aria-label={isPresenterMode ? "Exit Presenter Mode" : "Present with HRIDAY"}
            >
              <Sparkles size={14} />
              <span className="btn-label-responsive">{isPresenterMode ? "Exit" : "Present with voice"}</span>
            </button>
            <span className="symbolic-tooltip">
              {isPresenterMode ? "Exit Fullscreen Presenter Mode" : "Present with Autonomous Acoustic HRIDAY Voiceover"}
            </span>
          </div>

          {/* Royalty-Free Image Picker Trigger */}
          <div className="symbolic-btn-wrap">
            <button
              type="button"
              className="symbolic-action-btn"
              onClick={() => setIsImagePickerOpen(true)}
              aria-label="Browse Royalty-Free Commercial Photography"
            >
              <Image size={14} />
              <span className="btn-label-responsive">Photo</span>
            </button>
            <span className="symbolic-tooltip">
              Slide Photography: Browse free commercial photos with dark contrast scrim
            </span>
          </div>

          {/* Speaker Notes Drawer Toggle */}
          <div className="symbolic-btn-wrap">
            <button
              type="button"
              className={`symbolic-action-btn ${speakerNotesOpen ? "active" : ""}`}
              onClick={() => setSpeakerNotesOpen(!speakerNotesOpen)}
              aria-label="Toggle Speaker Notes"
            >
              <FileText size={14} />
              <span className="btn-label-responsive">Notes</span>
            </button>
            <span className="symbolic-tooltip">
              Speaker Notes: Executive talking points and speech script
            </span>
          </div>

          {/* Add Slide */}
          <div className="symbolic-btn-wrap">
            <button
              type="button"
              className="symbolic-action-btn"
              disabled={evidenceLocked}
              onClick={() => onAddSlide("blank")}
              aria-label="Append a New Slide"
            >
              <Plus size={14} />
              <span className="btn-label-responsive">Add</span>
            </button>
            <span className="symbolic-tooltip">
              Add Slide: Append a new executive slide to current deck
            </span>
          </div>

          {/* Export Options */}
          {onExportPptx && (
            <div className="symbolic-btn-wrap">
              <button
                type="button"
                className="symbolic-action-btn btn-export-pptx"
                onClick={onExportPptx}
                aria-label="Download PowerPoint PPTX"
              >
                <Download size={14} />
                <span className="btn-label-responsive">PPTX</span>
              </button>
              <span className="symbolic-tooltip">
                Export PPTX: Native PowerPoint presentation with editable charts
              </span>
            </div>
          )}

          {/* PDF Export */}
          <div className="symbolic-btn-wrap">
            <button
              type="button"
              className="symbolic-action-btn"
              onClick={handlePrintPdf}
              aria-label="Export PDF"
            >
              <Printer size={14} />
              <span className="btn-label-responsive">PDF</span>
            </button>
            <span className="symbolic-tooltip">
              Export PDF: Print or save presentation as PDF document
            </span>
          </div>
        </div>
      </fieldset>

      <fieldset className="studio-main-grid pres-editor-fieldset" disabled={isBusy}>
        {/* LEFT: SLIDE THUMBNAIL RAIL */}
        {!isPresenterMode && (
          <div className="studio-thumbnails-rail" role="region" aria-label="Slide thumbnail navigation">
            <div className="thumbnails-scroll-wrap">
              {deckSpec.slides.map((s, idx) => {
                const isActive = idx === activeSlideIndex;
                return (
                  <div
                    key={s.id || idx}
                    role="button"
                    tabIndex={0}
                    aria-current={isActive ? "true" : undefined}
                    aria-label={`Slide ${idx + 1}: ${s.title || "Untitled"}`}
                    className={`thumbnail-card ${isActive ? "active" : ""}`}
                    onClick={() => setActiveSlideIndex(idx)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setActiveSlideIndex(idx);
                      }
                    }}
                  >
                    <div className="thumb-header">
                      <span className="thumb-idx">{idx + 1}</span>
                      <span className="thumb-layout-tag">{s.layout?.replace(/_/g, " ")}</span>
                    </div>
                    <div className="thumb-title-preview">{s.title}</div>

                    {/* Thumbnail slide actions */}
                    <div className="thumb-actions" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="btn-thumb-action"
                        disabled={idx === 0}
                        onClick={() => onMoveSlide(idx, -1)}
                        title="Move slide up"
                        aria-label="Move slide up"
                      >
                        <ArrowUp size={12} />
                      </button>
                      <button
                        type="button"
                        className="btn-thumb-action"
                        disabled={idx === deckSpec.slides.length - 1}
                        onClick={() => onMoveSlide(idx, 1)}
                        title="Move slide down"
                        aria-label="Move slide down"
                      >
                        <ArrowDown size={12} />
                      </button>
                      <button
                        type="button"
                        className="btn-thumb-action"
                        disabled={evidenceLocked}
                        onClick={() => onDuplicateSlide(idx)}
                        title="Duplicate slide"
                        aria-label="Duplicate slide"
                      >
                        <Copy size={12} />
                      </button>
                      <button
                        type="button"
                        className="btn-thumb-action danger"
                        disabled={evidenceLocked}
                        onClick={() => onDeleteSlide(idx)}
                        title="Delete slide"
                        aria-label="Delete slide"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* CENTER: 16:9 STAGE & COPILOT PROMPT CURATION BAR */}
        <div className="studio-presenter-center">
          {/* Human Approval Checkpoint Banner */}
          {showApprovalBanner && (
            <div className="pres-approval-banner">
              <div className="banner-left">
                <Sparkles size={14} className="sparkle-anim" />
                <span>HRIDAY refined this slide. Review the adjustments:</span>
              </div>
              <div className="banner-actions">
                <button type="button" className="btn-approve" onClick={handleAcceptChanges}>
                  <Check size={13} />
                  <span>Accept Changes</span>
                </button>
                <button type="button" className="btn-revert" onClick={handleRevertChanges}>
                  <RotateCcw size={13} />
                  <span>Revert</span>
                </button>
              </div>
            </div>
          )}

          {/* 16:9 Presentation Stage */}
          {!isPresenterMode && <PresentationRevealDeck
            deckId={deckSpec.id}
            deckSpec={deckSpec}
            slides={deckSpec.slides}
            theme={currentTheme}
            activeSlideIndex={activeSlideIndex}
            onSlideChange={setActiveSlideIndex}
            readOnly={evidenceLocked || isBusy}
            isEditable={!evidenceLocked}
            onUpdateSlide={onUpdateSlide}
            onViewEvidence={onOpenEvidence}
            onExportHtml={() => exportStandaloneHtmlPresentation(deckSpec, selectedThemeId)}
          />}

          {/* HRIDAY CURATION PROMPT BAR (Below Active Slide) */}
          {!isPresenterMode && (
            <div
              className="studio-copilot-bar hriday-curation-bar"
              role="region"
              aria-label="HRIDAY Slide Editor"
            >
              <div className="copilot-bar-top">
                <div
                  className="copilot-badge hriday-badge"
                >
                  <Sparkles size={13} aria-hidden="true" />
                  <span>HRIDAY · Slide editor</span>
                </div>
                <details className="studio-suggestions">
                  <summary>Suggested refinements</summary>
                <div
                  className="suggestion-pills"
                  role="group"
                  aria-label="Curation suggestions"
                >
                  {SUGGESTION_PROMPTS.map((sug, i) => (
                    <button
                      key={i}
                      type="button"
                      className="suggestion-pill"
                      onClick={() => handleApplyCopilotCuration(sug)}
                      disabled={isCurating || isBusy}
                      aria-label={`Prompt HRIDAY to ${sug}`}
                      title={`Apply prompt: ${sug}`}
                    >
                      {sug}
                    </button>
                  ))}
                </div>
                </details>
              </div>

              <p className="copilot-status" role="status" aria-live="polite" aria-atomic="true">
                {isCurating ? "HRIDAY is refining this slide. Please wait."
                  : showApprovalBanner ? "Slide refined. Review the changes before accepting."
                  : ""}
              </p>
              {curationError && <p role="alert" className="copilot-error-msg">{curationError}</p>}
              <form
                className="copilot-input-row"
                onSubmit={(e) => {
                  e.preventDefault();
                  handleApplyCopilotCuration();
                }}
              >
                <input
                  type="text"
                  value={curatePrompt}
                  onChange={(e) => setCuratePrompt(e.target.value)}
                  placeholder="Ask HRIDAY to refine this slide (e.g. 'Rephrase for the CFO', 'Make bullet points sharper')..."
                  aria-label="Ask HRIDAY to refine this slide"
                  className="copilot-input"
                  disabled={isCurating || isBusy}
                />
                <button
                  type="submit"
                  disabled={isCurating || isBusy || !curatePrompt.trim()}
                  className="btn-curate btn-hriday-curate"
                  aria-label={isCurating ? "Refining slide..." : "Refine with HRIDAY"}
                >
                  {isCurating ? (
                    <>
                      <Zap size={14} className="spin-icon" aria-hidden="true" />
                      <span>Refining...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={14} aria-hidden="true" />
                      <span>Refine with HRIDAY</span>
                    </>
                  )}
                </button>
              </form>
            </div>
          )}

          {/* BOTTOM SPEAKER NOTES DRAWER */}
          {speakerNotesOpen && currentSlide && (
            <div className="studio-speaker-notes-bar" role="region" aria-label="Speaker notes">
              <div className="notes-bar-header">
                <div className="notes-header-left">
                  <FileText size={14} />
                  <span>Speaker Notes (Slide {activeSlideIndex + 1})</span>
                </div>
                <span className="notes-hint">Spoken by AI Orb in Web Presenter Mode · Exported to PPTX</span>
              </div>
              <textarea
                className="notes-textarea"
                readOnly={evidenceLocked}
                rows={2}
                value={currentSlide.speaker_notes || ""}
                aria-label={`Speaker notes for slide ${activeSlideIndex + 1}`}
                onChange={(e) => {
                  const updated = { ...currentSlide, speaker_notes: e.target.value };
                  onUpdateSlide(activeSlideIndex, updated);
                }}
                placeholder="Add talking points and executive narrative remarks..."
              />
            </div>
          )}
        </div>
      </fieldset>

      {/* Royalty-Free Image Picker Modal */}
      <SlideImagePickerModal
        isOpen={isImagePickerOpen}
        onClose={() => setIsImagePickerOpen(false)}
        onSelectImage={handleSelectImage}
        currentImageUrl={currentSlide?.background_image}
      />

      {/* Standalone Fullscreen Presenter Mode with Floating Orb */}
      {isPresenterMode && (
        <div className="theater-orb-overlay">
          <div className="theater-orb-stage">
            <PresentationRevealDeck
              deckId={deckSpec.id}
              deckSpec={deckSpec}
              slides={deckSpec.slides}
              theme={currentTheme}
              activeSlideIndex={activeSlideIndex}
              onSlideChange={setActiveSlideIndex}
              readOnly={true}
              isEditable={false}
              onUpdateSlide={onUpdateSlide}
              onViewEvidence={onOpenEvidence}
              onExportHtml={() => exportStandaloneHtmlPresentation(deckSpec, selectedThemeId)}
            />
            <AcousticOrbPresenter
              deckId={deckSpec.id}
              deckSpec={deckSpec}
              currentSlideOrder={activeSlideIndex + 1}
              totalSlides={deckSpec.slides.length}
              onAdvanceSlide={() => setActiveSlideIndex(Math.min(deckSpec.slides.length - 1, activeSlideIndex + 1))}
              onPrevSlide={() => setActiveSlideIndex(Math.max(0, activeSlideIndex - 1))}
            />
          </div>
          <button
            type="button"
            className="theater-exit-btn"
            onClick={() => setIsPresenterMode(false)}
            title="Exit Fullscreen Presenter Mode"
          >
            <Minimize2 size={16} />
            <span>Exit Presenter Mode</span>
          </button>
        </div>
      )}
    </div>
  );
}
