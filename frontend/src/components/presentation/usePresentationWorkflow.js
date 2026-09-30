import { useState, useEffect, useRef, useCallback } from "react";
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
import { exportStandaloneHtmlPresentation } from "../../utils/standaloneHtmlExporter";

export const STAGES = [
  { id: "layout", label: "Layout build up", desc: "Freezing snapshot and assembling layout wireframes" },
  { id: "headings", label: "Title & subpage headings", desc: "Outlining deck title, section categories, and slide titles" },
  { id: "data_math", label: "Mathematical derivation", desc: "Computing exact totals, percentages, and evidence ledgers" },
  { id: "narrative_ai", label: "AI storyline & narrative", desc: "Synthesizing executive findings, storylines, and insights" },
  { id: "enrichment", label: "Executive tone & narrative polish", desc: "Refining language, C-suite tone, and executive subtitles slide by slide" },
  { id: "graphics", label: "Graphic content", desc: "Rendering charts, metric cards, and visual callouts" },
  { id: "text", label: "Text content & density audit", desc: "Validating evidence claims and auditing spatial density" },
  { id: "animation", label: "Animation", desc: "Configuring entrance, emphasis, and motion cues" },
  { id: "transitions", label: "Transitions", desc: "Setting smooth slide-to-slide progression" },
  { id: "transcript", label: "HRIDAY voiceover transcript", desc: "Synthesizing executive talking points and speech notes" },
  { id: "formatting", label: "Final setup & PPTX/PDF formatting", desc: "Layout spatial audit, quality repair, and file generation" },
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
  const [targetLength, setTargetLength] = useState(null);
  const [deckStyle, setDeckStyle] = useState("standard");
  const [selectedThemeId, setSelectedThemeId] = useState("executive_dark");
  const [selectedSheetId, setSelectedSheetId] = useState("");
  const [instructions, setInstructions] = useState("");
  const [autoDownload, setAutoDownload] = useState(false);

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
  const generationOptionsRef = useRef({});
  const saveQueue = useRef(Promise.resolve());
  const deckRef = useRef(deckSpec);
  deckRef.current = deckSpec;
  const commitDeck = (updated) => {
    deckRef.current = updated;
    setDeckSpec(updated);
    onJobUpdate({ id: currentJobId, status: "ready", deck: updated });
    if (updated.id) {
      saveQueue.current = saveQueue.current.catch(() => {}).then(() => updatePresentationDeck(updated.id, updated))
        .catch(err => setJobError(`Your changes remain in this session, but saving failed: ${err.message}`));
    }
  };

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
          setSelectedSheetId(current => {
            if (current && res.sheets.some(s => String(s.id) === String(current))) {
              return current;
            }
            const urlSheetId = new URLSearchParams(window.location.search).get("sheet_id");
            if (urlSheetId && res.sheets.some(s => String(s.id) === String(urlSheetId))) {
              return urlSheetId;
            }
            return String(res.sheets[0].id);
          });
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
    } else {
      try {
        const params = new URLSearchParams(window.location.search);
        const urlDeckId = params.get("deck_id");
        if (urlDeckId) {
          getPresentationDeck(urlDeckId)
            .then(res => {
              const d = res.deck || res;
              if (d && d.slides) {
                setDeckSpec(d);
                setViewMode("studio");
              }
            })
            .catch(console.error);
        }
      } catch {}
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
        if (job.current_slide !== undefined || job.total_slides !== undefined || job.slide_status_list) {
          setSlideProgressData((prev) => {
            // Layman explanation:
            // Use the real-time slide status list sent from the backend so that
            // 'building' (active) and 'complete' (checked) states reflect actual progress.
            let updatedList = Array.isArray(job.slide_status_list) && job.slide_status_list.length > 0
              ? job.slide_status_list
              : (prev?.slide_status_list || []);

            // Fallback merge only if backend didn't supply full slide_status_list
            if ((!job.slide_status_list || job.slide_status_list.length === 0) && job.current_slide && job.current_slide_title) {
              const listCopy = [...updatedList];
              const existingIdx = listCopy.findIndex((s) => s.order === job.current_slide);
              if (existingIdx >= 0) {
                listCopy[existingIdx] = {
                  ...listCopy[existingIdx],
                  title: job.current_slide_title,
                  category: job.current_slide_category || listCopy[existingIdx].category,
                  status: "complete",
                };
              } else {
                listCopy.push({
                  order: job.current_slide,
                  title: job.current_slide_title,
                  category: job.current_slide_category || "",
                  status: "complete",
                });
                listCopy.sort((a, b) => a.order - b.order);
              }
              updatedList = listCopy;
            }

            return {
              current_slide: job.current_slide !== undefined ? job.current_slide : (prev?.current_slide || 0),
              total_slides: job.total_slides || prev?.total_slides || (updatedList.length || 0),
              current_slide_title: job.current_slide_title || prev?.current_slide_title || "",
              current_slide_category: job.current_slide_category || prev?.current_slide_category || "",
              slide_status_list: updatedList,
              observer_note: job.observer_note || prev?.observer_note || "",
              active_phase: job.active_phase || prev?.active_phase || job.stage || "layout",
            };
          });
        }

        if (job.status === "ready") {
          let deck = job.deck;
          if (!deck && job.deck_id) {
            try {
              const response = await getPresentationDeck(job.deck_id);
              deck = response.deck || response;
            } catch (deckErr) {
              console.error("Failed to fetch ready deck:", deckErr);
            }
          }

          if (deck) {
            setDeckSpec(deck);
            setJobProgress(100);
            setJobStage("ready");
            setJobStageLabel("Presentation deck verified & ready");
            onJobUpdate({ ...job, deck });

            setTimeout(() => {
              if (isMounted) {
                setViewMode("studio");
                if (autoDownload) {
                  exportPresentationPptx(deck).catch((dlErr) => console.warn("Auto-download PowerPoint failed:", dlErr));
                }
              }
            }, 800);
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

        pollTimerRef.current = setTimeout(poll, 250);
      } catch (err) {
        console.error("Job polling error:", err);
        setJobStageLabel("Connection interrupted. Reconnecting to the generation job…");
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

  // Handlers (Memoized for render performance and reliability)
  const handleStartGeneration = useCallback(async (options = generationOptionsRef.current) => {
    generationOptionsRef.current = options;
    setViewMode("generating");
    setCurrentJobId(null);
    setJobStage("layout");
    setJobProgress(0);
    setJobError(null);
    setSlideProgressData(null);
    try {
      const scope = {
        objective: options.customPrompt || options.objective || objective,
        audience: options.audience || audience,
        target_length: options.targetLength ?? targetLength,
        deck_style: deckStyle,
        theme_id: options.themeId || selectedThemeId,
        scope_type: options.scopeType || (selectedSheetId ? "single_sheet" : scopeType),
        sheet_id: selectedSheetId ? Number(selectedSheetId) : null,
        sheet_ids: scopeType === "custom_sheets" ? customSheetIds.map(Number) : [],
        group_id: scopeType === "connected_group" && selectedGroupId !== "" ? Number(selectedGroupId) : null,
        instructions: [instructions, options.instructions].filter(Boolean).join("\n"),
        source_mode: options.sourceMode || "dashboard_truth",
        background_image: options.selectedImageUrl || null,
        scrim_opacity: options.scrimOpacity ?? 70,
        transition: options.transitionStyle || "none",
        animation: options.animation || "none",
      };
      const res = await startPresentationGeneration(scope);
      setCurrentJobId(res.job_id);
      setJobProgress(5);
      setJobStage("layout");
      setJobStageLabel("Initiating workspace presentation pipeline...");
      setViewMode("generating");
      onJobUpdate({ ...res, progress_pct: 5, deck: null, status: "in_progress" });
    } catch (err) {
      setJobError(err.message || "Failed to start presentation generation");
    }
  }, [objective, audience, targetLength, deckStyle, selectedThemeId, selectedSheetId, scopeType, customSheetIds, selectedGroupId, instructions, onJobUpdate]);

  const handleGoBackToConfig = useCallback((force = false) => {
    if (force !== true && ((viewMode === "generating" && !jobError) || isRegeneratingSlide)) return;
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    setJobError(null);
    setCurrentJobId(null);
    setSlideProgressData(null);
    setJobProgress(0);
    setJobStage("layout");
    setViewMode("config");
  }, [viewMode, jobError, isRegeneratingSlide]);

  const handleResetAndStartGeneration = useCallback(() => {
    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    setJobError(null);
    setCurrentJobId(null);
    setSlideProgressData(null);
    if (sheets && sheets.length > 0 && !sheets.some(s => String(s.id) === String(selectedSheetId))) {
      const fallbackId = String(sheets[0].id);
      setSelectedSheetId(fallbackId);
      handleStartGeneration({ sheet_id: Number(fallbackId) });
    } else {
      handleStartGeneration();
    }
  }, [handleStartGeneration, sheets, selectedSheetId]);

  const handleCancelGeneration = useCallback(async () => {
    if (!currentJobId) {
      handleGoBackToConfig();
      return;
    }
    try {
      await cancelPresentationJob(currentJobId);
      handleGoBackToConfig(true);
    } catch (err) {
      setJobError(`Cancellation failed: ${err.message}`);
    }
  }, [currentJobId, handleGoBackToConfig]);

  const handleSwitchTheme = useCallback((themeId) => {
    if (!deckRef.current) return;
    setSelectedThemeId(themeId);
    const matchedTheme = themes.find(t => t.id === themeId);
    if (!matchedTheme) return;

    const updated = {
      ...deckRef.current,
      metadata: { ...deckRef.current.metadata, theme_id: themeId },
      theme: matchedTheme
    };
    commitDeck(updated);
  }, [themes]);

  const handleUpdateSlide = useCallback((slideIndex, updatedSlide) => {
    const latest = deckRef.current;
    if (!latest?.slides[slideIndex]) return;
    const slides = latest.slides.map((slide, idx) => idx === slideIndex
      ? { ...updatedSlide, provenance: "USER_OVERRIDE" } : slide);
    commitDeck({ ...latest, slides });
  }, []);

  const handleMoveSlide = useCallback((index, direction) => {
    const latest = deckRef.current;
    if (!latest) return;
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= latest.slides.length) return;

    const newSlides = [...latest.slides];
    const temp = newSlides[index];
    newSlides[index] = newSlides[newIndex];
    newSlides[newIndex] = temp;
    newSlides.forEach((s, idx) => { s.order = idx + 1; });

    const updated = { ...latest, slides: newSlides };
    commitDeck(updated);
    setActiveSlideIndex(newIndex);
  }, []);

  const handleDeleteSlide = useCallback((index) => {
    const latest = deckRef.current;
    if (!latest || latest.slides.length <= 1) {
      setJobError("A presentation must retain at least one slide.");
      return;
    }
    const newSlides = latest.slides.filter((_, i) => i !== index);
    newSlides.forEach((s, idx) => { s.order = idx + 1; });

    const updated = { ...latest, slides: newSlides };
    commitDeck(updated);
    setActiveSlideIndex(prev => Math.max(0, Math.min(prev, newSlides.length - 1)));
  }, []);

  const handleDuplicateSlide = useCallback((index) => {
    const latest = deckRef.current;
    if (!latest) return;
    const target = latest.slides[index];
    const duplicated = JSON.parse(JSON.stringify(target));
    duplicated.id = `slide_${Date.now()}`;
    duplicated.title = `${duplicated.title} (Copy)`;

    const newSlides = [...latest.slides];
    newSlides.splice(index + 1, 0, duplicated);
    newSlides.forEach((s, idx) => { s.order = idx + 1; });

    const updated = { ...latest, slides: newSlides };
    commitDeck(updated);
    setActiveSlideIndex(index + 1);
  }, []);

  const handleAddSlide = useCallback((layoutFamily = "chart_narrative") => {
    const latest = deckRef.current;
    if (!latest) return;
    const isBlank = layoutFamily === "blank";
    const isTitle = layoutFamily === "title_cover";
    const isImage = layoutFamily === "image_story";
    const isComparison = layoutFamily === "comparison_split";

    const newSlide = {
      id: `slide_${Date.now()}`,
      order: latest.slides.length + 1,
      layout: isBlank ? "blank" : isTitle ? "title_cover" : isImage ? "image_story" : isComparison ? "comparison_split" : "chart_narrative",
      category: isTitle ? "EXECUTIVE OVERVIEW" : isImage ? "OPERATIONAL SNAPSHOT" : "OPERATIONAL HIGHLIGHT",
      title: isBlank ? "Blank Slide" : isTitle ? "Executive Overview" : "New Strategic Slide",
      subtitle: isBlank ? "" : "Operational analysis and key recommendations",
      narrative: isBlank ? "" : "Synthesized observations regarding current dataset throughput and trends.",
      bullets: isBlank ? [] : [
        "First key analytical finding identified from data audit.",
        "Recommended operational next step for leadership review."
      ],
      metrics: isBlank ? [] : [
        { label: "Throughput", value: "Optimal", subtext: "Target range" }
      ],
      chart: null,
      table: null,
      speaker_notes: isBlank ? "" : "Add key talking points and presentation remarks here.",
      evidence_sources: ["HighView Ground Truth Engine · Verified Provenance"]
    };

    const newSlides = [...latest.slides, newSlide];
    const updated = { ...latest, slides: newSlides };
    commitDeck(updated);
    setActiveSlideIndex(newSlides.length - 1);
  }, []);

  const handleSetSlideImage = useCallback(({ url, scrimOpacity = 70, applyToAll = false }) => {
    const latest = deckRef.current;
    if (!latest) return;
    commitDeck({ ...latest, slides: latest.slides.map((slide, idx) =>
      applyToAll || idx === activeSlideIndex
        ? { ...slide, background_image: url, scrim_opacity: scrimOpacity, provenance: "USER_OVERRIDE" }
        : slide) });
  }, [activeSlideIndex]);

  const handleSetTransition = useCallback((transitionType) => {
    const latest = deckRef.current;
    if (!latest) return;
    const updated = {
      ...latest,
      metadata: { ...latest.metadata, transition: transitionType }
    };
    commitDeck(updated);
  }, []);

  const handleRegenerateSlideSubmit = useCallback(async (promptOverride) => {
    const prompt = typeof promptOverride === "string" ? promptOverride : regeneratePrompt;
    const latest = deckRef.current;
    if (!latest || !prompt.trim() || isRegeneratingSlide) return null;
    const currentSlide = latest.slides[activeSlideIndex];
    if (!currentSlide) return null;

    setIsRegeneratingSlide(true);
    try {
      const updated = await regenerateSlide(latest, currentSlide.id, prompt);
      commitDeck(updated);
      setShowRegenModal(false);
      setRegeneratePrompt("");
      return updated;
    } catch (err) {
      setJobError(`Regeneration failed: ${err.message}`);
      return null;
    } finally {
      setIsRegeneratingSlide(false);
    }
  }, [regeneratePrompt, isRegeneratingSlide, activeSlideIndex]);

  const handleExportPptx = useCallback(async () => {
    const latest = deckRef.current;
    if (latest) {
      setIsExportingPptx(true);
      try {
        await exportPresentationPptx(latest);
      } catch (err) {
        setJobError(`PowerPoint export failed: ${err.message}`);
      } finally {
        setIsExportingPptx(false);
      }
      return;
    }
    if (currentJobId) {
      try {
        const job = await getPresentationJob(currentJobId);
        const did = job?.deck_id;
        if (did) window.open(`/api/presentations/download/${did}`, "_blank");
      } catch (err) {
        setJobError(`PowerPoint export failed: ${err.message}`);
      }
    }
  }, [currentJobId]);

  const handleOpenInStudio = useCallback(async () => {
    if (deckRef.current) {
      setViewMode("studio");
      return;
    }
    if (currentJobId) {
      try {
        const job = await getPresentationJob(currentJobId);
        if (job?.deck) {
          commitDeck(job.deck);
          setViewMode("studio");
        } else if (job?.deck_id) {
          const res = await getPresentationDeck(job.deck_id);
          const d = res.deck || res;
          if (d) {
            commitDeck(d);
            setViewMode("studio");
          }
        }
      } catch (err) {
        setJobError(`Unable to open studio: ${err.message}`);
      }
    }
  }, [currentJobId]);

  const handleExportHtml = useCallback(async () => {
    const latest = deckRef.current;
    if (latest) {
      exportStandaloneHtmlPresentation(latest, selectedThemeId);
      return;
    }
    if (currentJobId) {
      try {
        const job = await getPresentationJob(currentJobId);
        const did = job?.deck_id;
        if (did) {
          const res = await getPresentationDeck(did);
          const d = res.deck || res;
          if (d) exportStandaloneHtmlPresentation(d, selectedThemeId);
        }
      } catch (err) {
        setJobError(`HTML export failed: ${err.message}`);
      }
    }
  }, [selectedThemeId, currentJobId]);

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
  };
}
