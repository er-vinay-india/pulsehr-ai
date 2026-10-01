import React, { useState, useEffect, useCallback, useRef } from "react";
import "../styles/presentation-responsive.scss";
import { AlertCircle, X } from "lucide-react";
import {
  getAdaptiveDashboardPrimaryElement,
  getLatestPresentationDeck,
  deletePresentationDeck,
  getDatasetPersonas
} from "../api/client";
import EvidenceInspectionDrawer from "../components/EvidenceInspectionDrawer.jsx";
import DeckGeneratingView from "../components/presentation/DeckGeneratingView.jsx";
import DeckStudioView from "../components/presentation/DeckStudioView.jsx";
import PromptStudioScreen from "../components/presentation/PromptStudioScreen.jsx";
import SlideRegenModal from "../components/presentation/SlideRegenModal.jsx";
import PresentationPageHeader from "../components/presentation/PresentationPageHeader.jsx";
import { usePresentationWorkflow, STAGES } from "../components/presentation/usePresentationWorkflow";

export default function PresentationPage({
  activeJobId = null,
  initialDeck = null,
  initialScopeType = "workspace",
  onJobUpdate = () => {}
}) {
  const {
    viewMode,
    configSession,
    handleNewDeck,
    setViewMode,
    themes,
    sheets,
    selectedThemeId,
    selectedSheetId,
    setSelectedSheetId,
    setObjective,
    setInstructions,
    currentJobId,
    jobProgress,
    jobStage,
    jobStageLabel,
    jobError,
    setJobError,
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
    handleExportPptx,
    handleOpenInStudio,
    handleExportHtml
  } = usePresentationWorkflow({
    isOpen: true,
    activeJobId,
    initialDeck,
    initialScopeType,
    onJobUpdate
  });
  const configRef = useRef(null);
  useEffect(() => {
    if (!configSession) return;
    configRef.current?.scrollIntoView({ block: "start" });
    configRef.current?.querySelector("button")?.focus({ preventScroll: true });
  }, [configSession]);

  // Active Dashboard Truth preview state
  const [dashboardData, setDashboardData] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);

  // Latest Generated Deck & Detected Industry Persona State
  const [latestDeck, setLatestDeck] = useState(null);
  const [detectedPersona, setDetectedPersona] = useState(null);
  const [relevantPersonas, setRelevantPersonas] = useState([]);

  const loadLatestDeck = useCallback(async () => {
    try {
      const res = await getLatestPresentationDeck();
      if (res && res.exists && res.deck) {
        setLatestDeck(res.deck);
      } else {
        setLatestDeck(null);
      }
    } catch (err) {
      console.debug("Could not fetch latest presentation:", err);
      setLatestDeck(null);
    }
  }, []);

  useEffect(() => {
    loadLatestDeck();
  }, [loadLatestDeck]);

  // Auto-detect matching industry standard persona whenever active sheet changes
  useEffect(() => {
    if (!selectedSheetId) return;
    getDatasetPersonas(selectedSheetId)
      .then((res) => {
        if (res?.detected_persona) {
          setDetectedPersona(res.detected_persona);
          setObjective(res.detected_persona.standard_report_name);
        }
        if (res?.relevant_personas) {
          setRelevantPersonas(res.relevant_personas);
        }
      })
      .catch((err) => console.debug("Error loading dataset personas:", err));
  }, [selectedSheetId, setObjective]);

  const handleOpenLatestDeck = useCallback((deck) => {
    if (!deck) return;
    setDeckSpec(deck);
    setViewMode("studio");
  }, [setDeckSpec, setViewMode]);

  const handleDeleteLatestDeck = useCallback(async (deckId) => {
    if (!deckId) return;
    try {
      await deletePresentationDeck(deckId);
      setLatestDeck(null);
      setDeckSpec(null);
      loadLatestDeck();
    } catch (err) {
      setJobError(`Failed to delete presentation: ${err.message}`);
    }
  }, [setDeckSpec, setJobError, loadLatestDeck]);

  // Ingest Dashboard Context from sessionStorage if initiated from Adaptive Dashboard
  useEffect(() => {
    try {
      const rawCtx = sessionStorage.getItem("presentation_dashboard_context");
      if (rawCtx) {
        const parsed = JSON.parse(rawCtx);
        if (parsed?.sheetId || parsed?.sheet_id) {
          const sid = String(parsed.sheetId || parsed.sheet_id);
          if (!sheets || sheets.length === 0 || sheets.some(s => String(s.id) === sid)) {
            setSelectedSheetId(sid);
          } else if (sheets && sheets.length > 0) {
            setSelectedSheetId(String(sheets[0].id));
          }
        }
        if (parsed?.sheetTitle || parsed?.sheet_name) {
          setObjective(`Executive summary and decision-grade analysis for ${parsed.sheetTitle || parsed.sheet_name}`);
        }
        if (parsed?.instruction) setInstructions(parsed.instruction);
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
  }, [setSelectedSheetId, setObjective, setInstructions, sheets]);

  // Fetch primary dashboard element for truth binding
  useEffect(() => {
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
    if (!sheetId) return;

    const controller = new AbortController();
    setDashboardLoading(true);

    getAdaptiveDashboardPrimaryElement(sheetId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted && data) {
          setDashboardData(data);
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          console.debug("Failed to fetch dashboard data for presentation:", err);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setDashboardLoading(false);
        }
      });

    return () => {
      controller.abort();
      setDashboardLoading(false);
    };
  }, [selectedSheetId, sheets]);

  return (
    <div className="presentation-page-container">
      {/* Reusable Presentation Top Header */}
      <PresentationPageHeader
        viewMode={viewMode}
        deckSpec={deckSpec}
        currentTheme={currentTheme}
        isRegeneratingSlide={isRegeneratingSlide}
        isExportingPptx={isExportingPptx}
        onResetAndStartGeneration={handleResetAndStartGeneration}
        onGoBackToConfig={handleNewDeck}
        onExportHtml={handleExportHtml}
        onOpenRegenerateModal={() => setShowRegenModal(true)}
        onExportPptx={handleExportPptx}
        onReturnToDeck={() => setViewMode("studio")}
      />

      {/* Accessible Non-Blocking Global Error Banner */}
      {jobError && (
        <div className="pres-error-alert" role="alert" aria-live="assertive">
          <div className="alert-content">
            <AlertCircle size={16} />
            <span>{jobError}</span>
          </div>
          <button
            type="button"
            className="btn-dismiss-alert"
            onClick={() => setJobError(null)}
            aria-label="Dismiss message"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Main Presentation View Container */}
      <div className={`presentation-modal-shell presentation-page-shell mode-${viewMode}`}>
        {/* VIEW 1: PROMPT STUDIO SCREEN (AI Dashboard-to-Deck Configurator) */}
        <div ref={configRef} hidden={viewMode !== "config"}>
          <PromptStudioScreen
            key={configSession}
            dashboardData={dashboardData}
            onGenerateDeck={handleStartGeneration}
            isGenerating={viewMode === "generating"}
            themes={themes}
            sheets={sheets}
            selectedSheetId={selectedSheetId}
            onSelectSheet={setSelectedSheetId}
            latestDeck={latestDeck}
            onOpenLatestDeck={handleOpenLatestDeck}
            onDeleteLatestDeck={handleDeleteLatestDeck}
            detectedPersona={detectedPersona}
            relevantPersonas={relevantPersonas}
            error={jobError}
          />
        </div>

        {/* VIEW 2: REAL-TIME GENERATION PIPELINE PROGRESS STEPPER */}
        {viewMode === "generating" && (
          <DeckGeneratingView
            stages={STAGES}
            jobStage={jobStage}
            jobProgress={jobProgress}
            jobStageLabel={jobStageLabel}
            jobError={jobError}
            slideProgressData={slideProgressData}
            onOpenInStudio={handleOpenInStudio}
            onExportPptx={handleExportPptx}
            onExportHtml={handleExportHtml}
            onResetAndStartGeneration={handleResetAndStartGeneration}
            onGoBackToConfig={handleGoBackToConfig}
            onCancelGeneration={handleCancelGeneration}
          />
        )}

        {/* VIEW 3: INTERACTIVE STUDIO & POST-GEN SLIDE DECK EDITOR */}
        {viewMode === "studio" && deckSpec && (
          <DeckStudioView
            deckSpec={deckSpec}
            activeSlideIndex={activeSlideIndex}
            setActiveSlideIndex={(index) => {
              if (!isRegeneratingSlide) setActiveSlideIndex(index);
            }}
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
            onRefineSlide={handleRegenerateSlideSubmit}
            isBusy={isRegeneratingSlide}
            onApplyImage={handleSetSlideImage}
          />
        )}

        {/* SINGLE SLIDE REGENERATION MODAL */}
        <SlideRegenModal
          isOpen={showRegenModal}
          onClose={() => {
            if (!isRegeneratingSlide) setShowRegenModal(false);
          }}
          slideIndex={activeSlideIndex}
          slideTitle={deckSpec?.slides[activeSlideIndex]?.title}
          regeneratePrompt={regeneratePrompt}
          setRegeneratePrompt={setRegeneratePrompt}
          onSubmit={() => handleRegenerateSlideSubmit()}
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
