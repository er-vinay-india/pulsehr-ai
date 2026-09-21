import { useState, useEffect, useRef } from "react";
import {
  getPresentationThemes,
  startPresentationGeneration,
  getPresentationJob,
  getPresentationDeck,
  cancelPresentationJob,
  getSheets,
  updatePresentationDeck,
  regenerateSlide,
  exportPresentationPptx,
  previewPresentationScope
} from "../../api/client";

export const STAGES = [
  { id: "reviewing_coverage", label: "Reviewing Coverage", desc: "Evaluating eligible datasets, boundaries & date ranges" },
  { id: "validating_relationships", label: "Validating Relationships", desc: "Checking cross-sheet link integrity & foreign keys" },
  { id: "collecting_findings", label: "Collecting Findings", desc: "Capturing executive findings & freezing evidence ledger" },
  { id: "synthesizing_outcomes", label: "Synthesizing Outcomes", desc: "Computing macro operational outcomes & benchmarks" },
  { id: "building_slides", label: "Building Slides", desc: "Assembling executive slide deck layouts & visual charts" },
  { id: "verifying_claims", label: "Verifying Claims", desc: "Auditing deterministic claim numbers (±0.1%)" },
  { id: "ready", label: "Ready to Review", desc: "Presentation sealed with cryptographic snapshot hash" }
];

export function usePresentationWorkflow({
  isOpen,
  activeJobId = null,
  initialDeck = null,
  initialScopeType = "workspace",
  onJobUpdate = () => {}
}) {
  const [viewMode, setViewMode] = useState("config"); // "config" | "generating" | "studio"
  const [themes, setThemes] = useState([]);
  const [sheets, setSheets] = useState([]);

  // Scope form state
  const [scopeType, setScopeType] = useState(initialScopeType);
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const [customSheetIds, setCustomSheetIds] = useState([]);
  const [scopePreview, setScopePreview] = useState(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  // Core config form state
  const [objective, setObjective] = useState("Executive Leadership Review");
  const [audience, setAudience] = useState("C-Suite & Operations Leadership");
  const [targetLength, setTargetLength] = useState(8);
  const [deckStyle, setDeckStyle] = useState("decision_brief");
  const [selectedThemeId, setSelectedThemeId] = useState("bold_signal");
  const [selectedSheetId, setSelectedSheetId] = useState("");
  const [instructions, setInstructions] = useState("");
  const [autoDownload, setAutoDownload] = useState(true);

  // Job progress state
  const [currentJobId, setCurrentJobId] = useState(activeJobId);
  const [jobProgress, setJobProgress] = useState(0);
  const [jobStage, setJobStage] = useState("reviewing_coverage");
  const [jobStageLabel, setJobStageLabel] = useState("Initiating pipeline...");
  const [jobError, setJobError] = useState(null);
  const [slideProgressData, setSlideProgressData] = useState(null);

  // Studio deck state
  const [deckSpec, setDeckSpec] = useState(initialDeck);
  const [activeSlideIndex, setActiveSlideIndex] = useState(0);
  const [isExportingPptx, setIsExportingPptx] = useState(false);
  const [isRegeneratingSlide, setIsRegeneratingSlide] = useState(false);
  const [regeneratePrompt, setRegeneratePrompt] = useState("");
  const [showRegenModal, setShowRegenModal] = useState(false);
  const [speakerNotesOpen, setSpeakerNotesOpen] = useState(true);

  // Evidence Inspection Drawer state
  const [isEvidenceDrawerOpen, setIsEvidenceDrawerOpen] = useState(false);
  const [selectedEvidenceSlide, setSelectedEvidenceSlide] = useState(null);

  // Poll timer
  const pollTimerRef = useRef(null);

  // 1. Initial data fetch
  useEffect(() => {
    if (!isOpen) return;

    getPresentationThemes()
      .then(res => {
        if (res.themes) setThemes(res.themes);
      })
      .catch(console.error);

    getSheets()
      .then(res => {
        if (res.sheets && res.sheets.length > 0) {
          setSheets(res.sheets);
          if (!selectedSheetId) {
            setSelectedSheetId(String(res.sheets[0].id));
          }
          setCustomSheetIds(res.sheets.map(s => String(s.id)));
        }
      })
      .catch(console.error);
  }, [isOpen]);

  // 2. Preflight Scope Preview live auditor
  useEffect(() => {
    if (!isOpen || viewMode !== "config") return;

    let isMounted = true;
    setIsLoadingPreview(true);

    const payload = {
      scope_type: scopeType,
      sheet_id: selectedSheetId ? Number(selectedSheetId) : null,
      sheet_ids: scopeType === "custom_sheets" ? customSheetIds.map(Number) : [],
      group_id: scopeType === "connected_group" && selectedGroupId !== "" ? Number(selectedGroupId) : null
    };

    previewPresentationScope(payload)
      .then(res => {
        if (isMounted) {
          setScopePreview(res);
          if (res.connected_groups && res.connected_groups.length > 0 && selectedGroupId === "") {
            setSelectedGroupId(String(res.connected_groups[0].group_id));
          }
        }
      })
      .catch(err => {
        console.warn("Preflight scope preview error:", err);
      })
      .finally(() => {
        if (isMounted) setIsLoadingPreview(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, viewMode, scopeType, selectedSheetId, customSheetIds, selectedGroupId]);

  // 3. Initial viewMode determination
  useEffect(() => {
    if (initialDeck) {
      setDeckSpec(initialDeck);
      setViewMode("studio");
    } else if (activeJobId) {
      setCurrentJobId(activeJobId);
      setViewMode("generating");
    }
  }, [initialDeck, activeJobId]);

  // 4. Polling for background job
  useEffect(() => {
    if (viewMode !== "generating" || !currentJobId) return;

    let isMounted = true;

    const poll = async () => {
      try {
        const job = await getPresentationJob(currentJobId);
        if (!isMounted) return;

        onJobUpdate(job);
        setJobProgress(job.progress_pct || 0);
        setJobStage(job.stage);
        setJobStageLabel(job.stage_label || "Processing...");
        if (job.current_slide || job.total_slides) {
          setSlideProgressData({
            current_slide: job.current_slide || 0,
            total_slides: job.total_slides || 0,
            current_slide_title: job.current_slide_title || "",
            current_slide_category: job.current_slide_category || "",
            slide_status_list: job.slide_status_list || []
          });
        }

        if (job.status === "ready") {
          let deck = job.deck;
          if (!deck && job.deck_id) {
            try {
              deck = await getPresentationDeck(job.deck_id);
            } catch (deckErr) {
              console.error("Failed to fetch ready deck:", deckErr);
            }
          }

          if (deck) {
            setDeckSpec(deck);
            setViewMode("studio");
            onJobUpdate({ ...job, deck });

            if (autoDownload) {
              try {
                await exportPresentationPptx(deck);
              } catch (dlErr) {
                console.warn("Auto-download PowerPoint failed:", dlErr);
              }
            }
            return;
          }
        }

        if (job.status === "failed") {
          setJobError(job.error || "Generation pipeline encountered an error.");
          return;
        }

        if (job.status === "cancelled") {
          setViewMode("config");
          return;
        }

        pollTimerRef.current = setTimeout(poll, 1500);
      } catch (err) {
        console.error("Job polling error:", err);
        if (isMounted) {
          pollTimerRef.current = setTimeout(poll, 2500);
        }
      }
    };

    poll();

    return () => {
      isMounted = false;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [viewMode, currentJobId, autoDownload]);

  // Handlers
  const handleStartGeneration = async () => {
    setJobError(null);
    setDeckSpec(null);
    setSlideProgressData(null);
    try {
      const scope = {
        objective,
        audience,
        target_length: Number(targetLength),
        deck_style: deckStyle,
        theme_id: selectedThemeId,
        scope_type: scopeType,
        sheet_id: selectedSheetId ? Number(selectedSheetId) : null,
        sheet_ids: scopeType === "custom_sheets" ? customSheetIds.map(Number) : [],
        group_id: scopeType === "connected_group" && selectedGroupId !== "" ? Number(selectedGroupId) : null,
        instructions
      };
      const res = await startPresentationGeneration(scope);
      setCurrentJobId(res.job_id);
      setJobProgress(5);
      setJobStage("reviewing_coverage");
      setJobStageLabel("Initiating workspace presentation pipeline...");
      setViewMode("generating");
      onJobUpdate({ ...res, progress_pct: 5, deck: null, status: "in_progress" });
    } catch (err) {
      setJobError(err.message || "Failed to start presentation generation");
    }
  };

  const handleGoBackToConfig = () => {
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    setJobError(null);
    setCurrentJobId(null);
    setDeckSpec(null);
    setSlideProgressData(null);
    setJobProgress(0);
    setJobStage("reviewing_coverage");
    setViewMode("config");
    onJobUpdate(null);
  };

  const handleResetAndStartGeneration = () => {
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    setJobError(null);
    setCurrentJobId(null);
    setDeckSpec(null);
    setSlideProgressData(null);
    handleStartGeneration();
  };

  const handleCancelGeneration = async () => {
    if (!currentJobId) {
      handleGoBackToConfig();
      return;
    }
    try {
      await cancelPresentationJob(currentJobId);
      handleGoBackToConfig();
    } catch (err) {
      console.error("Cancel job error:", err);
      handleGoBackToConfig();
    }
  };

  const handleSwitchTheme = (themeId) => {
    if (!deckSpec) return;
    const matchedTheme = themes.find(t => t.id === themeId);
    if (!matchedTheme) return;

    const updated = {
      ...deckSpec,
      metadata: { ...deckSpec.metadata, theme_id: themeId },
      theme: matchedTheme
    };
    setDeckSpec(updated);
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleUpdateSlide = (slideIndex, updatedSlide) => {
    if (!deckSpec) return;
    const newSlides = [...deckSpec.slides];
    newSlides[slideIndex] = updatedSlide;
    const updated = { ...deckSpec, slides: newSlides };
    setDeckSpec(updated);
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleMoveSlide = (index, direction) => {
    if (!deckSpec) return;
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= deckSpec.slides.length) return;

    const newSlides = [...deckSpec.slides];
    const temp = newSlides[index];
    newSlides[index] = newSlides[newIndex];
    newSlides[newIndex] = temp;
    newSlides.forEach((s, idx) => { s.order = idx + 1; });

    const updated = { ...deckSpec, slides: newSlides };
    setDeckSpec(updated);
    setActiveSlideIndex(newIndex);
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleDeleteSlide = (index) => {
    if (!deckSpec || deckSpec.slides.length <= 1) {
      alert("A presentation must retain at least one slide.");
      return;
    }
    const newSlides = deckSpec.slides.filter((_, i) => i !== index);
    newSlides.forEach((s, idx) => { s.order = idx + 1; });

    const updated = { ...deckSpec, slides: newSlides };
    setDeckSpec(updated);
    setActiveSlideIndex(Math.max(0, Math.min(activeSlideIndex, newSlides.length - 1)));
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleDuplicateSlide = (index) => {
    if (!deckSpec) return;
    const target = deckSpec.slides[index];
    const duplicated = JSON.parse(JSON.stringify(target));
    duplicated.id = `slide_${Date.now()}`;
    duplicated.title = `${duplicated.title} (Copy)`;

    const newSlides = [...deckSpec.slides];
    newSlides.splice(index + 1, 0, duplicated);
    newSlides.forEach((s, idx) => { s.order = idx + 1; });

    const updated = { ...deckSpec, slides: newSlides };
    setDeckSpec(updated);
    setActiveSlideIndex(index + 1);
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleAddSlide = () => {
    if (!deckSpec) return;
    const newSlide = {
      id: `slide_${Date.now()}`,
      order: deckSpec.slides.length + 1,
      layout: "chart_narrative",
      category: "OPERATIONAL HIGHLIGHT",
      title: "New Strategic Slide",
      subtitle: "Operational analysis and key recommendations",
      narrative: "Synthesized observations regarding current dataset throughput and trends.",
      bullets: [
        "First key analytical finding identified from data audit.",
        "Recommended operational next step for leadership review."
      ],
      metrics: [
        { label: "Throughput", value: "Optimal", subtext: "Target range" }
      ],
      chart: null,
      table: null,
      speaker_notes: "Add key talking points and presentation remarks here.",
      evidence_sources: ["PulseHR Ground Truth Engine"]
    };

    const newSlides = [...deckSpec.slides, newSlide];
    const updated = { ...deckSpec, slides: newSlides };
    setDeckSpec(updated);
    setActiveSlideIndex(newSlides.length - 1);
    updatePresentationDeck(updated.id, updated).catch(console.error);
  };

  const handleRegenerateSlideSubmit = async () => {
    if (!deckSpec || !regeneratePrompt.trim()) return;
    const currentSlide = deckSpec.slides[activeSlideIndex];
    if (!currentSlide) return;

    setIsRegeneratingSlide(true);
    try {
      const updated = await regenerateSlide(deckSpec, currentSlide.id, regeneratePrompt);
      setDeckSpec(updated);
      setShowRegenModal(false);
      setRegeneratePrompt("");
    } catch (err) {
      alert(`Regeneration failed: ${err.message}`);
    } finally {
      setIsRegeneratingSlide(false);
    }
  };

  const handleExportPptx = async () => {
    if (!deckSpec) return;
    setIsExportingPptx(true);
    try {
      await exportPresentationPptx(deckSpec);
    } catch (err) {
      alert(`PowerPoint export failed: ${err.message}`);
    } finally {
      setIsExportingPptx(false);
    }
  };

  const currentTheme = deckSpec?.theme || themes.find(t => t.id === selectedThemeId) || {
    bg_color: "#171412",
    card_bg: "#201b18",
    card_border: "#3d362f",
    primary_text: "#fff9f2",
    secondary_text: "#beb2a6",
    brand_color: "#ff8a62",
    accent_color: "#7ee7d9"
  };

  return {
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
  };
}
