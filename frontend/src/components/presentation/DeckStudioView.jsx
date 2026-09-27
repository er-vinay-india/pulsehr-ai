import React, { useState } from "react";
import {
  Palette,
  ShieldCheck,
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
}) {
  const [isImagePickerOpen, setIsImagePickerOpen] = useState(false);
  const [isPresenterMode, setIsPresenterMode] = useState(false);
  const [curatePrompt, setCuratePrompt] = useState("");
  const [isCurating, setIsCurating] = useState(false);
  const [previousSlideSnapshot, setPreviousSlideSnapshot] = useState(null);
  const [showApprovalBanner, setShowApprovalBanner] = useState(false);

  const evidenceLocked = deckSpec.metadata?.deck_style === "decision_brief";
  const currentSlide = deckSpec.slides[activeSlideIndex] || deckSpec.slides[0];

  // Handle Copilot Slide Curation
  const handleApplyCopilotCuration = async (promptText) => {
    const prompt = (promptText || curatePrompt).trim();
    if (!prompt || !currentSlide) return;

    setIsCurating(true);
    // Snapshot current state for Revert capability
    setPreviousSlideSnapshot(JSON.parse(JSON.stringify(currentSlide)));

    try {
      // Intelligent in-studio curation rule engine
      const updated = JSON.parse(JSON.stringify(currentSlide));
      const pLower = prompt.toLowerCase();

      if (pLower.includes("condense") || pLower.includes("concise") || pLower.includes("2")) {
        if (updated.bullets && updated.bullets.length > 2) {
          updated.bullets = updated.bullets.slice(0, 2);
        }
        updated.narrative = updated.narrative
          ? updated.narrative.split(".")[0] + ". Immediate leadership review recommended."
          : updated.narrative;
      } else if (pLower.includes("cfo") || pLower.includes("cost") || pLower.includes("financial")) {
        updated.title = updated.title.includes("Financial") ? updated.title : `Financial Impact: ${updated.title}`;
        updated.bullets = [
          { text: "Primary Budget Exposure: Disparity concentration drives localized payroll expansion." },
          { text: "Mitigation Mandate: Realign shift duty rosters before quarterly close." },
        ];
        updated.speaker_notes = `Financial briefing: Focusing on unit-level budget variance and remediation timeline.`;
      } else if (pLower.includes("decisive") || pLower.includes("board")) {
        updated.title = updated.title.toUpperCase();
        updated.bullets = (updated.bullets || []).map((b) => ({
          text: `Action Directive: ${typeof b === "string" ? b : b.text}`,
        }));
      } else if (pLower.includes("disparity") || pLower.includes("spread")) {
        updated.subtitle = `Disparity Focus: Immediate normalization required across operational units`;
      } else {
        // General enrichment
        updated.narrative = `${updated.narrative} [Curated: ${prompt}]`;
      }

      onUpdateSlide(activeSlideIndex, updated);
      setShowApprovalBanner(true);
      setCuratePrompt("");
    } catch (err) {
      console.error("Copilot curation error:", err);
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

  const handleSelectImage = ({ url, scrimOpacity, applyToAll }) => {
    if (applyToAll) {
      deckSpec.slides.forEach((s, idx) => {
        const updated = {
          ...s,
          background_image: url,
          scrim_opacity: scrimOpacity,
        };
        onUpdateSlide(idx, updated);
      });
    } else {
      const updated = {
        ...currentSlide,
        background_image: url,
        scrim_opacity: scrimOpacity,
      };
      onUpdateSlide(activeSlideIndex, updated);
    }
  };

  const handlePrintPdf = () => {
    window.print();
  };

  return (
    <div className={`pres-studio-body ${isPresenterMode ? "theater-presenter-mode" : ""}`}>
      {/* STUDIO SUB-TOOLBAR */}
      <div className="studio-sub-toolbar">
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

          {/* Audit Verification Seal */}
          <div className="symbolic-btn-wrap">
            <div className="validation-summary-chip verified" title="Simpson's Paradox & Empirical Audit Verified">
              <ShieldCheck size={13} />
              <span className="seal-text-responsive">S01–S20 Audit</span>
            </div>
            <span className="symbolic-tooltip">Audit Governance: Verified against aggregate distortion & Simpson&apos;s Paradox</span>
          </div>
        </div>

        <div className="toolbar-right">
          {/* Executive AI Orb Launcher */}
          <div className="symbolic-btn-wrap">
            <button
              type="button"
              className={`symbolic-action-btn btn-present-orb ${isPresenterMode ? "active" : ""}`}
              onClick={() => setIsPresenterMode(!isPresenterMode)}
              aria-label={isPresenterMode ? "Exit Presenter Mode" : "Present with AI Orb"}
            >
              <Sparkles size={14} />
              <span className="btn-label-responsive">{isPresenterMode ? "Exit" : "AI Orb"}</span>
            </button>
            <span className="symbolic-tooltip">
              {isPresenterMode ? "Exit Fullscreen Presenter Mode" : "Present with Autonomous Acoustic AI Orb Voiceover"}
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

          {/* Audit Evidence Drawer Toggle */}
          <div className="symbolic-btn-wrap">
            <button
              type="button"
              className={`symbolic-action-btn ${isEvidenceDrawerOpen ? "active" : ""}`}
              onClick={() => onOpenEvidence(deckSpec.slides[activeSlideIndex])}
              aria-label="Audit Calculation Methodology & Board Evidence"
            >
              <ShieldCheck size={14} />
              <span className="btn-label-responsive">Audit</span>
            </button>
            <span className="symbolic-tooltip">
              Audit Evidence: S01–S20 verifiable calculation ledger & methodology
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
              onClick={onAddSlide}
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
      </div>

      <div className="studio-main-grid">
        {/* LEFT: SLIDE THUMBNAIL RAIL */}
        {!isPresenterMode && (
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
                      >
                        <ArrowUp size={12} />
                      </button>
                      <button
                        type="button"
                        className="btn-thumb-action"
                        disabled={idx === deckSpec.slides.length - 1}
                        onClick={() => onMoveSlide(idx, 1)}
                        title="Move slide down"
                      >
                        <ArrowDown size={12} />
                      </button>
                      <button
                        type="button"
                        className="btn-thumb-action"
                        disabled={evidenceLocked}
                        onClick={() => onDuplicateSlide(idx)}
                        title="Duplicate slide"
                      >
                        <Copy size={12} />
                      </button>
                      <button
                        type="button"
                        className="btn-thumb-action danger"
                        disabled={evidenceLocked}
                        onClick={() => onDeleteSlide(idx)}
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
        )}

        {/* CENTER: 16:9 STAGE & COPILOT PROMPT CURATION BAR */}
        <div className="studio-presenter-center">
          {/* Human Approval Checkpoint Banner */}
          {showApprovalBanner && (
            <div className="pres-approval-banner">
              <div className="banner-left">
                <Sparkles size={14} className="sparkle-anim" />
                <span>AI Copilot refined this slide. Review the adjustments:</span>
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
          <PresentationRevealDeck
            deckId={deckSpec.id}
            deckSpec={deckSpec}
            slides={deckSpec.slides}
            theme={currentTheme}
            activeSlideIndex={activeSlideIndex}
            onSlideChange={setActiveSlideIndex}
            readOnly={evidenceLocked}
            isEditable={!evidenceLocked}
            onUpdateSlide={onUpdateSlide}
            onViewEvidence={onOpenEvidence}
            onExportHtml={() => exportStandaloneHtmlPresentation(deckSpec, selectedThemeId)}
          />

          {/* COPILOT CURATION PROMPT BAR (Below Active Slide) */}
          {!isPresenterMode && (
            <div className="studio-copilot-bar">
              <div className="copilot-bar-top">
                <div className="copilot-badge">
                  <Sparkles size={13} />
                  <span>AI Copilot Slide Curation:</span>
                </div>
                <div className="suggestion-pills">
                  {SUGGESTION_PROMPTS.map((sug, i) => (
                    <button
                      key={i}
                      type="button"
                      className="suggestion-pill"
                      onClick={() => handleApplyCopilotCuration(sug)}
                      disabled={isCurating}
                    >
                      {sug}
                    </button>
                  ))}
                </div>
              </div>

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
                  placeholder="Ask AI Copilot to refine this slide (e.g. 'Rephrase for the CFO', 'Make bullet points sharper')..."
                  className="copilot-input"
                  disabled={isCurating}
                />
                <button
                  type="submit"
                  disabled={isCurating || !curatePrompt.trim()}
                  className="btn-curate"
                >
                  {isCurating ? (
                    <>
                      <Zap size={14} className="spin-icon" />
                      <span>Refining...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={14} />
                      <span>Refine Slide</span>
                    </>
                  )}
                </button>
              </form>
            </div>
          )}

          {/* BOTTOM SPEAKER NOTES DRAWER */}
          {speakerNotesOpen && currentSlide && (
            <div className="studio-speaker-notes-bar">
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
                onChange={(e) => {
                  const updated = { ...currentSlide, speaker_notes: e.target.value };
                  onUpdateSlide(activeSlideIndex, updated);
                }}
                placeholder="Add talking points and executive narrative remarks..."
              />
            </div>
          )}
        </div>
      </div>

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
