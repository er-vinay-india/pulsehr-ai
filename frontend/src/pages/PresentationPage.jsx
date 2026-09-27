import React from "react";
import "../styles/presentation-responsive.scss";
import {
  Presentation,
  Download,
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
import EvidenceInspectionDrawer from "../components/EvidenceInspectionDrawer.jsx";
import { exportStandaloneHtmlPresentation } from "../utils/standaloneHtmlExporter";
import DeckConfigView from "../components/presentation/DeckConfigView.jsx";
import DeckGeneratingView from "../components/presentation/DeckGeneratingView.jsx";
import DeckStudioView from "../components/presentation/DeckStudioView.jsx";
import PromptStudioScreen from "../components/presentation/PromptStudioScreen.jsx";
import SlideRegenModal from "../components/presentation/SlideRegenModal.jsx";
import { transformDashboardToDeck, transformCustomPromptToDeck } from "../utils/dashboardToPresentation";
import { usePresentationWorkflow, STAGES } from "../components/presentation/usePresentationWorkflow";

export default function PresentationPage({
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
    handleSetSlideImage,
    handleSetTransition,
    handleRegenerateSlideSubmit,
    handleExportPptx
  } = usePresentationWorkflow({
    isOpen: true,
    activeJobId,
    initialDeck,
    initialScopeType,
    onJobUpdate
  });

  // Active Dashboard Truth Fetching
  const [dashboardData, setDashboardData] = React.useState(null);
  const [dashboardLoading, setDashboardLoading] = React.useState(false);
  const [useAdvancedScopeForm, setUseAdvancedScopeForm] = React.useState(false);

  // Ingest Dashboard Context from sessionStorage if initiated from Adaptive Dashboard
  React.useEffect(() => {
    try {
      const rawCtx = sessionStorage.getItem("presentation_dashboard_context");
      if (rawCtx) {
        const parsed = JSON.parse(rawCtx);
        if (parsed?.sheetId) {
          setSelectedSheetId(String(parsed.sheetId));
        }
        if (parsed?.sheetTitle) {
          setObjective(`Executive summary and decision-grade analysis for ${parsed.sheetTitle}`);
        }
        if (parsed?.activeFilters && Object.keys(parsed.activeFilters).length > 0) {
          const filterStr = Object.entries(parsed.activeFilters)
            .map(([k, v]) => `${k}: ${v}`)
            .join(", ");
          setInstructions(`Dashboard context with active filters: ${filterStr}`);
        }
      }
    } catch (err) {
      console.warn("Failed reading presentation dashboard context from sessionStorage", err);
    }
  }, [setSelectedSheetId, setObjective, setInstructions]);

  React.useEffect(() => {
    let sheetId = selectedSheetId;
    if (!sheetId) {
      try {
        const params = new URLSearchParams(window.location.search);
        sheetId = params.get("sheet_id");
      } catch {}
    }
    if (!sheetId && sheets && sheets.length > 0) {
      sheetId = String(sheets[0].id);
    }
    if (sheetId) {
      setDashboardLoading(true);
      fetch(`/api/adaptive-dashboard/primary-element?sheet_id=${sheetId}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data) setDashboardData(data);
        })
        .catch((err) => console.debug("Failed to fetch dashboard data for presentation:", err))
        .finally(() => setDashboardLoading(false));
    }
  }, [selectedSheetId, sheets]);

  const handleGenerateFromDashboard = (options) => {
    if (options?.themeId) setSelectedThemeId(options.themeId);
    if (options?.targetLength) setTargetLength(options.targetLength);
    if (options?.customPrompt) setObjective(options.customPrompt);

    if (options?.sourceMode === "custom_prompt" && options?.customPrompt) {
      const generatedDeck = transformCustomPromptToDeck(options.customPrompt, options, dashboardData);
      if (generatedDeck) {
        setDeckSpec(generatedDeck);
        setViewMode("studio");
        setActiveSlideIndex(0);
        return;
      }
    }
    if (dashboardData) {
      const generatedDeck = transformDashboardToDeck(dashboardData, options);
      if (generatedDeck) {
        setDeckSpec(generatedDeck);
        setViewMode("studio");
        setActiveSlideIndex(0);
        return;
      }
    }
    // Fallback if no dashboard data available
    handleStartGeneration();
  };

  return (
    <div className="presentation-page-container">
      {/* Standardized Page Top Section */}
      <header className="page-top-header presentation-page-header">
        <div className="page-title-row">
          <div className="page-title-group">
            <h1 className="page-heading">
              {viewMode === "config" && (useAdvancedScopeForm ? "Presentation Scope & Setup" : "Presentation Studio")}
              {viewMode === "generating" && "Generating Presentation Deck"}
              {viewMode === "studio" && (deckSpec?.metadata?.title || "Presentation Studio")}
            </h1>
            <p className="page-description">
              {viewMode === "config" && (useAdvancedScopeForm ? "Configure multi-sheet dataset boundaries, analytical scope, and evidence ledger parameters." : "AI-assisted slide deck generation from ground-truth sheet findings and executive insights.")}
              {viewMode === "generating" && "Running 6-stage background analytical intelligence pipeline..."}
              {viewMode === "studio" && `${deckSpec?.slides?.length || 0} slides · ${currentTheme?.name || "Theme"} · Frontend Slides 16:9 Stage`}
            </p>
          </div>

          <div className="header-actions-row">
            {viewMode === "config" && (
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={() => setUseAdvancedScopeForm(!useAdvancedScopeForm)}
                title={useAdvancedScopeForm ? "Switch to AI Prompt Studio" : "Configure Custom Datasets and Advanced Scope"}
              >
                <Sliders size={14} />
                <span>{useAdvancedScopeForm ? "Switch to Prompt Studio" : "Advanced Scope Form"}</span>
              </button>
            )}

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
          </div>
        </div>
      </header>

      <div className={`presentation-modal-shell presentation-page-shell mode-${viewMode}`}>

        {/* VIEW 1: PROMPT STUDIO SCREEN (AI Dashboard-to-Deck) */}
        {viewMode === "config" && !useAdvancedScopeForm && (
          <PromptStudioScreen
            dashboardData={dashboardData}
            onGenerateDeck={handleGenerateFromDashboard}
            isGenerating={dashboardLoading}
            themes={themes}
          />
        )}

        {/* LEGACY VIEW 1 FALLBACK: ADVANCED SCOPE FORM */}
        {viewMode === "config" && useAdvancedScopeForm && (
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
                getPresentationJob(currentJobId).then((j) => {
                  if (j?.deck) {
                    setDeckSpec(j.deck);
                    setViewMode("studio");
                  } else if (j?.deck_id) {
                    getPresentationDeck(j.deck_id).then((d) => {
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
                getPresentationJob(currentJobId).then((j) => {
                  const did = j?.deck_id;
                  if (did) window.open(`/api/presentations/download/${did}`, "_blank");
                });
              }
            }}
            onExportHtml={() => {
              if (deckSpec) {
                exportStandaloneHtmlPresentation(deckSpec, selectedThemeId);
              } else if (currentJobId) {
                getPresentationJob(currentJobId).then((j) => {
                  const did = j?.deck_id;
                  if (did) {
                    getPresentationDeck(did).then((d) => {
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
            onExportPptx={handleExportPptx}
            selectedThemeId={selectedThemeId}
            onSetSlideImage={handleSetSlideImage}
            onSetTransition={handleSetTransition}
            onOpenRegenerate={() => setShowRegenModal(true)}
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
