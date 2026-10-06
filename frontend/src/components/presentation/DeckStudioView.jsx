import { useSlideLayout } from './slides/ResolvedSlideContent.jsx';
import { exportPresentationPdf, mutatePresentationSlide } from '../../api/client.js';
import DeckControl from './DeckControl.jsx';
import Select from '../common/Select.jsx';
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
  ShieldCheck,
  ListOrdered,
} from "lucide-react";
import PresentationRevealDeck from "../PresentationRevealDeck.jsx";
import { exportStandaloneHtmlPresentation } from "../../utils/standaloneHtmlExporter";
import SlideImagePickerModal from "./SlideImagePickerModal.jsx";
import ReviewGatesModal from "./ReviewGatesModal.jsx";
import AcousticOrbPresenter from "./AcousticOrbPresenter.jsx";
import AnimatedAcousticOrb from "./AnimatedAcousticOrb.jsx";

const SUGGESTION_PROMPTS = [
  "Switch chart to variance waterfall",
  "Convert chart to breakdown tree",
  "Group by Location instead of Department",
  "Highlight disparity spread & cost risk",
  "Condense to 2 high-impact takeaways",
  "Change theme to executive dark",
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
  onReorderPresentation,
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
  const [isSlideOptionsOpen, setIsSlideOptionsOpen] = useState(false);
  const [pdfExporting, setPdfExporting] = useState(false);
  const [pdfError, setPdfError] = useState('');
  const [isImagePickerOpen, setIsImagePickerOpen] = useState(false);
  const [isReviewGatesOpen, setIsReviewGatesOpen] = useState(false);
  const [isPresenterMode, setIsPresenterMode] = useState(false);
  const [curatePrompt, setCuratePrompt] = useState("");
  const [isCurating, setIsCurating] = useState(false);
  const [curationError, setCurationError] = useState("");
  const [previousSlideSnapshot, setPreviousSlideSnapshot] = useState(null);
  const [showApprovalBanner, setShowApprovalBanner] = useState(false);
  const [mutationSummary, setMutationSummary] = useState("");
  const notesPanelRef = React.useRef(null);
  const shouldRevealNotes = React.useRef(false);

  // Listen for real-time conversational mutations dispatched from Hriday Chat
  React.useEffect(() => {
    const handleDeckMutated = (event) => {
      const mut = event.detail;
      if (!mut || !mut.updated_deck_spec) return;
      if (mut.previous_slide_snapshot) {
        setPreviousSlideSnapshot(mut.previous_slide_snapshot);
      }
      if (mut.slide_index !== undefined && mut.slide_index !== null) {
        setActiveSlideIndex(mut.slide_index);
      }
      setMutationSummary(mut.diff_summary || "HRIDAY applied slide mutation.");
      setShowApprovalBanner(true);
      const newSlide = mut.updated_deck_spec.slides[mut.slide_index];
      if (newSlide) {
        onUpdateSlide(mut.slide_index, newSlide);
      }
    };
    window.addEventListener("presentation:deck-mutated", handleDeckMutated);
    return () => window.removeEventListener("presentation:deck-mutated", handleDeckMutated);
  }, [setActiveSlideIndex, onUpdateSlide]);

  React.useEffect(() => {
    if (window.matchMedia("(max-width: 768px)").matches) setSpeakerNotesOpen(false);
  }, [setSpeakerNotesOpen]);

  React.useEffect(() => {
    if (speakerNotesOpen && shouldRevealNotes.current) {
      notesPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      shouldRevealNotes.current = false;
    }
  }, [speakerNotesOpen]);

  const evidenceLocked = false; // Factual boundary: Editorial content freely editable; metrics tracked with USER_OVERRIDE
  const currentSlide = deckSpec.slides[activeSlideIndex] || deckSpec.slides[0];
  const { plan: currentLayout } = useSlideLayout(currentSlide, currentTheme);
  const handleExportHtml = async () => {
    setPdfError('');
    try {
      await exportStandaloneHtmlPresentation(deckSpec, selectedThemeId);
    } catch (error) {
      setPdfError(`HTML: ${error.message}`);
    }
  };

  // Handle Copilot Slide Curation & Deterministic Mutations
  const handleApplyCopilotCuration = async (promptText) => {
    const prompt = (promptText || curatePrompt).trim();
    if (!prompt || !currentSlide || isBusy || isCurating) return;

    setIsCurating(true);
    setPreviousSlideSnapshot(JSON.parse(JSON.stringify(currentSlide)));

    try {
      setCurationError("");
      const pLow = prompt.toLowerCase();

      // Check if prompt is a deterministic mutation
      let mutationAction = null;
      let mutationParams = {};

      if (pLow.includes("waterfall")) {
        mutationAction = "retype_chart";
        mutationParams = { chart_type: "waterfall" };
      } else if (pLow.includes("breakdown tree") || pLow.includes("tree")) {
        mutationAction = "retype_chart";
        mutationParams = { chart_type: "breakdown_tree" };
      } else if (pLow.includes("donut") || pLow.includes("pie")) {
        mutationAction = "retype_chart";
        mutationParams = { chart_type: "donut" };
      } else if (pLow.includes("theme")) {
        mutationAction = "change_theme";
        mutationParams = { theme_id: /amber|brush/.test(pLow) ? "amber_brush" : pLow.includes("dark") ? "executive_dark" : "corporate_navy" };
      } else if (pLow.includes("group by") || pLow.includes("slice by") || pLow.includes("by location")) {
        mutationAction = "reslice_slide";
        const dimMatch = prompt.match(/(?:group\s+by|slice\s+by|by)\s+([A-Za-z0-9_\s]+?)(?:\s+instead|\s*$|\.)/i);
        const dim = dimMatch ? dimMatch[1].trim() : "Location";
        mutationParams = { dimension_col: dim };
      }

      if (mutationAction) {
        const mutRes = await mutatePresentationSlide({
          deckSpec,
          action: mutationAction,
          params: mutationParams,
          slideIndex: activeSlideIndex,
          slideId: currentSlide.id,
          deckId: deckSpec.id,
          prompt
        });
        if (mutRes?.success) {
          const updatedSlide = mutRes.updated_deck_spec.slides[activeSlideIndex];
          if (updatedSlide) onUpdateSlide(activeSlideIndex, updatedSlide);
          setMutationSummary(mutRes.diff_summary);
          setShowApprovalBanner(true);
          setCuratePrompt("");
          return;
        }
      }

      // Fallback to text narrative refinement
      const result = await onRefineSlide(prompt);
      if (!result) { setCurationError("HRIDAY could not refine this slide. Your content is unchanged. Please try again."); return; }
      setMutationSummary("Slide narrative refined based on executive instructions.");
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
    setMutationSummary("");
  };

  const handleRevertChanges = () => {
    if (previousSlideSnapshot) {
      onUpdateSlide(activeSlideIndex, previousSlideSnapshot);
      setShowApprovalBanner(false);
      setPreviousSlideSnapshot(null);
      setMutationSummary("");
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

  const handlePrintPdf = async () => {
    setPdfExporting(true);
    setPdfError('');
    try { await exportPresentationPdf(deckSpec); }
    catch (error) { setPdfError(error.message); }
    finally { setPdfExporting(false); }
  };

  return (
    <div className={`pres-studio-body ${isPresenterMode ? "theater-presenter-mode" : ""}`}>
      {/* STUDIO SUB-TOOLBAR */}
      <fieldset className="studio-sub-toolbar pres-editor-fieldset" disabled={isBusy}>
        <div className="mobile-studio-navigation">
          <div className="mobile-slide-jump" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--color-text-secondary)', whiteSpace: 'nowrap' }}>Go to slide</span>
            <Select
              size="sm"
              value={String(activeSlideIndex)}
              onChange={e => setActiveSlideIndex(Number(e.target.value))}
              aria-label="Go to slide"
              options={deckSpec.slides.map((slide, index) => ({
                value: String(index),
                label: `${index + 1}. ${slide.title || "Untitled slide"}`
              }))}
              triggerStyle={{ minWidth: '150px', maxWidth: '240px' }}
            />
          </div>
          <button type="button" className="btn-secondary mobile-slide-options-toggle"
            aria-expanded={isSlideOptionsOpen} aria-controls="deck-slide-options"
            onClick={() => setIsSlideOptionsOpen(open => !open)}>
            <Sliders size={16} aria-hidden="true" />
            <span>Options</span>
          </button>
        </div>
        <div id="deck-slide-options" className={`toolbar-left ${isSlideOptionsOpen ? "mobile-options-open" : ""}`}>
          <span className="slide-counter-badge">
            Slide {activeSlideIndex + 1} of {deckSpec.slides.length}
          </span>

          <DeckControl className="symbolic-btn-wrap">
            <div className="theme-quick-dropdown">
              <Palette size={14} style={{ flexShrink: 0, color: 'var(--color-brand-secondary)' }} />
              <Select
                size="sm"
                value={deckSpec.theme?.id || deckSpec.metadata?.theme_id || "executive_dark"}
                onChange={(e) => onSwitchTheme(e.target.value)}
                aria-label="Switch Theme"
                options={themes.map((t) => ({
                  value: t.id,
                  label: t.name
                }))}
                triggerStyle={{ border: 'none', background: 'transparent', padding: '0 4px', minHeight: '30px' }}
              />
            </div>
            <span className="symbolic-tooltip">Visual Theme Palette</span>
          </DeckControl>

          <DeckControl className="symbolic-btn-wrap">
            <div className="theme-quick-dropdown">
              <Film size={14} style={{ flexShrink: 0, color: 'var(--color-brand-secondary)' }} />
              <Select
                size="sm"
                value={currentSlide.transition || deckSpec.metadata?.transition || "none"}
                onChange={(e) => {
                  const val = e.target.value;
                  onUpdateSlide(activeSlideIndex, { ...currentSlide, transition: val });
                }}
                aria-label="Slide Transition"
                options={[
                  { value: "none", label: "Transition: None" },
                  { value: "fade", label: "Transition: Fade" },
                  { value: "slide", label: "Transition: Slide" },
                  { value: "scale", label: "Transition: Scale" },
                  { value: "reveal", label: "Transition: Reveal" }
                ]}
                triggerStyle={{ border: 'none', background: 'transparent', padding: '0 4px', minHeight: '30px' }}
              />
            </div>
            <span className="symbolic-tooltip">Slide Transition Effect</span>
          </DeckControl>

          <DeckControl className="symbolic-btn-wrap">
            <div className="theme-quick-dropdown">
              <Sliders size={14} style={{ flexShrink: 0, color: 'var(--color-brand-secondary)' }} />
              <Select
                size="sm"
                value={currentSlide.layout || "chart_narrative"}
                onChange={(e) => {
                  const val = e.target.value;
                  onUpdateSlide(activeSlideIndex, { ...currentSlide, layout: val });
                }}
                aria-label="Slide Layout"
                options={[
                  { value: "chart_narrative", label: "Layout: Chart & Insights" },
                  { value: "full_chart_takeaway", label: "Layout: Hero Chart" },
                  { value: "two_charts", label: "Layout: Dual Charts" },
                  { value: "comparison_split", label: "Layout: Strategic Split" },
                  { value: "title_hero", label: "Layout: Executive Hero" },
                  { value: "image_story", label: "Layout: Visual Image Story" },
                  { value: "table_detail", label: "Layout: Evidence Table" },
                  { value: "title_cover", label: "Layout: Title Cover" }
                ]}
                triggerStyle={{ border: 'none', background: 'transparent', padding: '0 4px', minHeight: '30px' }}
              />
            </div>
            <span className="symbolic-tooltip">Slide Layout Variant</span>
          </DeckControl>
        </div>

        <div className="toolbar-right">
          {/* Executive AI Orb Launcher */}
          <DeckControl className="symbolic-btn-wrap">
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
          </DeckControl>

          {/* Royalty-Free Image Picker Trigger */}
          <DeckControl className="symbolic-btn-wrap">
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
          </DeckControl>

          {/* Speaker Notes Drawer Toggle */}
          <DeckControl className="symbolic-btn-wrap">
            <button
              type="button"
              className={`symbolic-action-btn ${speakerNotesOpen ? "active" : ""}`}
              onClick={() => {
                shouldRevealNotes.current = !speakerNotesOpen && window.matchMedia("(max-width: 768px)").matches;
                setSpeakerNotesOpen(!speakerNotesOpen);
              }}
              aria-label="Toggle Speaker Notes"
              aria-expanded={speakerNotesOpen}
              aria-controls="deck-speaker-notes"
            >
              <FileText size={14} />
              <span className="btn-label-responsive">Notes</span>
            </button>
            <span className="symbolic-tooltip">
              Speaker Notes: Executive talking points and speech script
            </span>
          </DeckControl>

          {/* 5 Review Gates Trigger */}
          <DeckControl className="symbolic-btn-wrap">
            <button
              type="button"
              className={`symbolic-action-btn ${isReviewGatesOpen ? "active" : ""}`}
              onClick={() => setIsReviewGatesOpen(true)}
              aria-label="Presentation Review Gates"
            >
              <ShieldCheck size={14} />
              <span className="btn-label-responsive">Review Gates</span>
            </button>
            <span className="symbolic-tooltip">
              5 Review Gates: Automated checks and explicit human sign-off audit
            </span>
          </DeckControl>

          {/* Add Slide */}
          <DeckControl className="symbolic-btn-wrap">
            <button
              type="button"
              className="symbolic-action-btn"
              disabled={evidenceLocked}
              onClick={() => onAddSlide("blank")}
              aria-label="Append a New Slide"
            >
              <Plus size={14} />
              <span className="btn-label-responsive">Add slide</span>
            </button>
            <span className="symbolic-tooltip">
              Add Slide: Append a new executive slide to current deck
            </span>
          </DeckControl>

          {/* Reorder Presentation */}
          {onReorderPresentation && (
            <DeckControl className="symbolic-btn-wrap">
              <button
                type="button"
                className="symbolic-action-btn"
                onClick={onReorderPresentation}
                aria-label="Reorder slides into canonical presentation sequence"
              >
                <ListOrdered size={14} />
                <span className="btn-label-responsive">Reorder</span>
              </button>
              <span className="symbolic-tooltip">
                Reorder Presentation: Position Title Cover at Slide 1 and sequence narrative
              </span>
            </DeckControl>
          )}

          {/* Export Options */}
          {onExportPptx && (
            <DeckControl className="symbolic-btn-wrap studio-pptx-action">
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
            </DeckControl>
          )}

          {/* PDF Export */}
          <DeckControl className="symbolic-btn-wrap">
            <button
              type="button"
              className="symbolic-action-btn"
              onClick={handlePrintPdf}
              disabled={pdfExporting}
              aria-busy={pdfExporting}
              aria-label="Export PDF"
            >
              <Printer size={14} />
              <span className="btn-label-responsive">PDF</span>
            </button>
            <span className="symbolic-tooltip">
              Export PDF with the same readable slide layout
            </span>
          </DeckControl>
        </div>
      </fieldset>

      {pdfError && <p role="alert" className="resolved-layout-message">Export failed: {pdfError}</p>}

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
                <span>{mutationSummary || "HRIDAY refined this slide. Review the adjustments:"}</span>
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
            onExportHtml={handleExportHtml}
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
                  placeholder="Ask HRIDAY to improve this slide..."
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
            <div ref={notesPanelRef} id="deck-speaker-notes" className="studio-speaker-notes-bar" role="region" aria-label="Speaker notes">
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
              {currentLayout?.supporting_notes?.length > 0 && <details className="notes-supporting-detail">
                <summary>Supporting detail included in export notes</summary>
                {currentLayout.supporting_notes.map((note, index) => <p key={index}>{note}</p>)}
              </details>}
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

      {/* Five Review Gates Modal */}
      <ReviewGatesModal
        isOpen={isReviewGatesOpen}
        onClose={() => setIsReviewGatesOpen(false)}
        deckSpec={deckSpec}
        onDeckUpdated={(updatedDeck) => {
          if (onUpdateSlide && updatedDeck?.slides?.[activeSlideIndex]) {
            onUpdateSlide(activeSlideIndex, updatedDeck.slides[activeSlideIndex]);
          }
        }}
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
              onExportHtml={handleExportHtml}
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
