import React from "react";
import {
  Presentation,
  Download,
  X,
  Sliders,
  Sparkles,
  RefreshCw,
  Plus
} from "lucide-react";
import {
  getPresentationJob,
  getPresentationDeck,
  exportPresentationPptx
} from "../api/client";
import EvidenceInspectionDrawer from "./EvidenceInspectionDrawer.jsx";
import { exportStandaloneHtmlPresentation } from "../utils/standaloneHtmlExporter";
import DeckConfigView from "./presentation/DeckConfigView.jsx";
import DeckGeneratingView from "./presentation/DeckGeneratingView.jsx";
import DeckStudioView from "./presentation/DeckStudioView.jsx";
import SlideRegenModal from "./presentation/SlideRegenModal.jsx";
import { usePresentationWorkflow, STAGES } from "./presentation/usePresentationWorkflow";

export default function CreatePresentationModal({
  isOpen,
  onClose,
  activeJobId = null,
  initialDeck = null,
  initialScopeType = "workspace",
  onJobUpdate = () => {}
}) {
  const {
    viewMode,
    setViewMode,
    themes,
    sheets,
    scopeType,
    setScopeType,
    selectedGroupId,
    setSelectedGroupId,
    customSheetIds,
    setCustomSheetIds,
    scopePreview,
    isLoadingPreview,
    objective,
    setObjective,
    audience,
    setAudience,
    targetLength,
    setTargetLength,
    deckStyle,
    setDeckStyle,
    selectedThemeId,
    setSelectedThemeId,
    selectedSheetId,
    setSelectedSheetId,
    instructions,
    setInstructions,
    autoDownload,
    setAutoDownload,
    currentJobId,
    jobProgress,
    jobStage,
    jobStageLabel,
    jobError,
    slideProgressData,
    deckSpec,
    setDeckSpec,
    activeSlideIndex,
    setActiveSlideIndex,
    isExportingPptx,
    isRegeneratingSlide,
    regeneratePrompt,
    setRegeneratePrompt,
    showRegenModal,
    setShowRegenModal,
    speakerNotesOpen,
    setSpeakerNotesOpen,
    isEvidenceDrawerOpen,
    setIsEvidenceDrawerOpen,
    selectedEvidenceSlide,
    setSelectedEvidenceSlide,
    currentTheme,
    handleStartGeneration,
    handleGoBackToConfig,
    handleResetAndStartGeneration,
    handleCancelGeneration,
    handleSwitchTheme,
    handleUpdateSlide,
    handleMoveSlide,
    handleDeleteSlide,
    handleDuplicateSlide,
    handleAddSlide,
    handleRegenerateSlideSubmit,
    handleExportPptx
  } = usePresentationWorkflow({
    isOpen,
    activeJobId,
    initialDeck,
    initialScopeType,
    onJobUpdate
  });

  if (!isOpen) return null;

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
                {viewMode === "config" && "Use the executive overview findings, with editable charts and evidence notes"}
                {viewMode === "generating" && "Running 6-stage background analytical intelligence pipeline"}
                {viewMode === "studio" && `${deckSpec?.slides?.length || 0} slides · ${currentTheme?.name || "Theme"} · Frontend Slides 16:9 Stage`}
              </p>
            </div>
          </div>

          <div className="header-actions-row">
            {viewMode === "generating" && (
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={handleGoBackToConfig}
                title="Return to configuration settings"
              >
                <Sliders size={14} />
                <span>Back to Setup</span>
              </button>
            )}

            {viewMode === "studio" && (
              <>
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={handleResetAndStartGeneration}
                  title="Regenerate presentation deck with fresh AI intelligence"
                >
                  <RefreshCw size={14} />
                  <span>Generate Again</span>
                </button>

                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={handleGoBackToConfig}
                  title="Configure and generate a new presentation"
                >
                  <Plus size={14} />
                  <span>New Deck</span>
                </button>

                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => exportStandaloneHtmlPresentation(deckSpec, selectedThemeId)}
                  title="Download Standalone Zero-Dependency HTML Presentation (Offline Presenter)"
                >
                  <Download size={14} />
                  <span>Download HTML</span>
                </button>

                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  disabled={deckSpec?.metadata?.deck_style === "decision_brief"}
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
          <DeckConfigView
            themes={themes}
            selectedThemeId={selectedThemeId}
            setSelectedThemeId={setSelectedThemeId}
            sheets={sheets}
            scopeType={scopeType}
            setScopeType={setScopeType}
            selectedGroupId={selectedGroupId}
            setSelectedGroupId={setSelectedGroupId}
            customSheetIds={customSheetIds}
            setCustomSheetIds={setCustomSheetIds}
            selectedSheetId={selectedSheetId}
            setSelectedSheetId={setSelectedSheetId}
            objective={objective}
            setObjective={setObjective}
            audience={audience}
            setAudience={setAudience}
            deckStyle={deckStyle}
            setDeckStyle={setDeckStyle}
            targetLength={targetLength}
            setTargetLength={setTargetLength}
            instructions={instructions}
            setInstructions={setInstructions}
            autoDownload={autoDownload}
            setAutoDownload={setAutoDownload}
            scopePreview={scopePreview}
            isLoadingPreview={isLoadingPreview}
            jobError={jobError}
            onStartGeneration={handleStartGeneration}
          />
        )}

        {/* VIEW 2: REAL-TIME GENERATION PIPELINE PROGRESS */}
        {viewMode === "generating" && (
          <DeckGeneratingView
            stages={STAGES}
            jobStage={jobStage}
            jobProgress={jobProgress}
            jobStageLabel={jobStageLabel}
            jobError={jobError}
            slideProgressData={slideProgressData}
            onOpenInStudio={() => {
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
            onExportPptx={() => {
              if (deckSpec) {
                exportPresentationPptx(deckSpec);
              } else if (currentJobId) {
                getPresentationJob(currentJobId).then(j => {
                  const did = j?.deck_id;
                  if (did) window.open(`/api/presentations/download/${did}`, "_blank");
                });
              }
            }}
            onExportHtml={() => {
              if (deckSpec) {
                exportStandaloneHtmlPresentation(deckSpec, selectedThemeId);
              } else if (currentJobId) {
                getPresentationJob(currentJobId).then(j => {
                  const did = j?.deck_id;
                  if (did) {
                    getPresentationDeck(did).then(d => {
                      if (d?.deck) exportStandaloneHtmlPresentation(d.deck, selectedThemeId);
                    });
                  }
                });
              }
            }}
            onResetAndStartGeneration={handleResetAndStartGeneration}
            onGoBackToConfig={handleGoBackToConfig}
            onCancelGeneration={handleCancelGeneration}
          />
        )}

        {/* VIEW 3: INTERACTIVE STUDIO & POST-GEN EDITOR */}
        {viewMode === "studio" && deckSpec && (
          <DeckStudioView
            deckSpec={deckSpec}
            activeSlideIndex={activeSlideIndex}
            setActiveSlideIndex={setActiveSlideIndex}
            themes={themes}
            onSwitchTheme={handleSwitchTheme}
            currentTheme={currentTheme}
            isEvidenceDrawerOpen={isEvidenceDrawerOpen}
            onOpenEvidence={(slide) => {
              setSelectedEvidenceSlide(slide);
              setIsEvidenceDrawerOpen(true);
            }}
            speakerNotesOpen={speakerNotesOpen}
            setSpeakerNotesOpen={setSpeakerNotesOpen}
            onAddSlide={handleAddSlide}
            onMoveSlide={handleMoveSlide}
            onDuplicateSlide={handleDuplicateSlide}
            onDeleteSlide={handleDeleteSlide}
            onUpdateSlide={handleUpdateSlide}
            selectedThemeId={selectedThemeId}
          />
        )}

        {/* SINGLE SLIDE REGENERATION MODAL */}
        <SlideRegenModal
          isOpen={showRegenModal}
          onClose={() => setShowRegenModal(false)}
          slideIndex={activeSlideIndex}
          slideTitle={deckSpec?.slides[activeSlideIndex]?.title}
          regeneratePrompt={regeneratePrompt}
          setRegeneratePrompt={setRegeneratePrompt}
          onSubmit={handleRegenerateSlideSubmit}
          isRegenerating={isRegeneratingSlide}
        />

        {/* EVIDENCE INSPECTION DRAWER */}
        <EvidenceInspectionDrawer
          isOpen={isEvidenceDrawerOpen}
          onClose={() => setIsEvidenceDrawerOpen(false)}
          slide={selectedEvidenceSlide || deckSpec?.slides?.[activeSlideIndex]}
          evidenceLedger={deckSpec?.evidence_ledger || deckSpec?.metadata?.evidence_ledger || []}
          snapshotHash={deckSpec?.metadata?.data_snapshot_hash || deckSpec?.metadata?.snapshot_hash}
          validationSummary={deckSpec?.metadata?.validation_summary}
          coverageManifest={deckSpec?.coverage_manifest || deckSpec?.metadata?.coverage_manifest}
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
