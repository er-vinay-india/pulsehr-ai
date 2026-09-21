import React from "react";
import {
  Palette,
  ShieldCheck,
  Clock,
  FileText,
  Plus,
  ArrowUp,
  ArrowDown,
  Copy,
  Trash2
} from "lucide-react";
import PresentationRevealDeck from "../PresentationRevealDeck.jsx";
import { exportStandaloneHtmlPresentation } from "../../utils/standaloneHtmlExporter";

export default function DeckStudioView({
  deckSpec,
  activeSlideIndex,
  setActiveSlideIndex,
  themes,
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
  selectedThemeId
}) {
  const evidenceLocked = deckSpec.metadata?.deck_style === "decision_brief";
  return (
    <div className="pres-studio-body">
      {/* STUDIO SUB-TOOLBAR */}
      <div className="studio-sub-toolbar">
        <div className="toolbar-left">
          <span className="slide-counter-badge">
            Slide {activeSlideIndex + 1} of {deckSpec.slides.length}
          </span>

          <div className="theme-quick-dropdown">
            <Palette size={14} />
            <select
              className="select-theme-inline"
              value={deckSpec.theme?.id || deckSpec.metadata?.theme_id || "executive_dark"}
              onChange={e => onSwitchTheme(e.target.value)}
            >
              {themes.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          {deckSpec.metadata?.validation_summary && (
            <div
              className={`validation-summary-chip ${String(deckSpec.metadata.validation_summary.status).toLowerCase() === "passed" ? "verified" : "flagged"}`}
              title={`Claim Verification: ${deckSpec.metadata.validation_summary.passed_verification} of ${deckSpec.metadata.validation_summary.total_metrics_checked} verified (${deckSpec.metadata.validation_summary.tolerance_threshold || "reported tolerance"})`}
            >
              <ShieldCheck size={13} />
              <span>
                {String(deckSpec.metadata.validation_summary.status).toLowerCase() === "passed"
                  ? `Verified · ${deckSpec.metadata.validation_summary.passed_verification}/${deckSpec.metadata.validation_summary.total_metrics_checked} checks`
                  : `${Array.isArray(deckSpec.metadata.validation_summary.discrepancies_flagged) ? deckSpec.metadata.validation_summary.discrepancies_flagged.length : (deckSpec.metadata.validation_summary.discrepancies_flagged ?? 0)} discrepancies flagged`}
              </span>
            </div>
          )}

          {deckSpec.metadata?.snapshot_hash && (
            <span className="snapshot-seal-chip" title={`Cryptographic Snapshot Hash: ${deckSpec.metadata.snapshot_hash}`}>
              SHA256: {deckSpec.metadata.snapshot_hash.slice(0, 8)}...
            </span>
          )}

          {deckSpec.metadata?.created_at && (
            <span className="snapshot-seal-chip" title={`Presentation Generated At: ${deckSpec.metadata.created_at}`}>
              <Clock size={12} style={{ marginRight: 4, display: "inline-block", verticalAlign: "middle" }} />
              <span>{new Date(deckSpec.metadata.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
            </span>
          )}
        </div>

        <div className="toolbar-right">
          <button
            type="button"
            className={`btn-ghost-sm ${isEvidenceDrawerOpen ? "active" : ""}`}
            onClick={() => onOpenEvidence(deckSpec.slides[activeSlideIndex])}
            title="Audit calculation methodology, board briefing & reproducible audit ledger"
          >
            <ShieldCheck size={14} />
            <span>Audit Evidence</span>
          </button>

          <button
            type="button"
            className={`btn-ghost-sm ${speakerNotesOpen ? "active" : ""}`}
            onClick={() => setSpeakerNotesOpen(!speakerNotesOpen)}
          >
            <FileText size={14} />
            <span>Speaker Notes</span>
          </button>

          <button
            type="button"
            className="btn-ghost-sm"
            disabled={evidenceLocked}
            onClick={onAddSlide}
            title="Add a new slide to deck"
          >
            <Plus size={14} />
            <span>Add Slide</span>
          </button>
        </div>
      </div>

      <div className="studio-main-grid">
        {/* LEFT: SLIDE THUMBNAIL RAIL */}
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
                    <span className="thumb-layout-tag">{s.layout?.replace("_", " ")}</span>
                  </div>
                  <div className="thumb-title-preview">{s.title}</div>

                  {/* Thumbnail slide actions */}
                  <div className="thumb-actions" onClick={e => e.stopPropagation()}>
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

        {/* CENTER: REVEAL.JS 16:9 PRESENTER */}
        <div className="studio-presenter-center">
          <PresentationRevealDeck
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

          {/* BOTTOM SPEAKER NOTES DRAWER */}
          {speakerNotesOpen && deckSpec.slides[activeSlideIndex] && (
            <div className="studio-speaker-notes-bar">
              <div className="notes-bar-header">
                <div className="notes-header-left">
                  <FileText size={14} />
                  <span>Speaker Notes (Slide {activeSlideIndex + 1})</span>
                </div>
                <span className="notes-hint">Exported into PowerPoint presenter view</span>
              </div>
              <textarea
                className="notes-textarea"
                readOnly={evidenceLocked}
                rows={2}
                value={deckSpec.slides[activeSlideIndex].speaker_notes || ""}
                onChange={e => {
                  const updated = { ...deckSpec.slides[activeSlideIndex], speaker_notes: e.target.value };
                  onUpdateSlide(activeSlideIndex, updated);
                }}
                placeholder="Add talking points and executive narrative remarks..."
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
