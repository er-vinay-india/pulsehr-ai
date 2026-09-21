import React from "react";
import { Sparkles, X } from "lucide-react";

export default function SlideRegenModal({
  isOpen,
  onClose,
  slideIndex,
  slideTitle,
  regeneratePrompt,
  setRegeneratePrompt,
  onSubmit,
  isRegenerating
}) {
  if (!isOpen) return null;

  return (
    <div className="pres-regen-dialog-backdrop">
      <div className="pres-regen-dialog">
        <div className="dialog-header">
          <div className="dialog-title-wrap">
            <Sparkles size={16} style={{ color: "var(--brand-500, #ff8a62)" }} />
            <h4>Regenerate Slide {slideIndex + 1}</h4>
          </div>
          <button
            type="button"
            className="btn-icon-close"
            onClick={onClose}
          >
            <X size={16} />
          </button>
        </div>

        <div className="dialog-body">
          <p className="dialog-hint">
            Current Title: <strong>{slideTitle}</strong>
          </p>
          <label htmlFor="regen-prompt">AI Guidance / Emphasis Prompt</label>
          <textarea
            id="regen-prompt"
            className="form-textarea"
            rows={3}
            value={regeneratePrompt}
            onChange={e => setRegeneratePrompt(e.target.value)}
            placeholder="e.g. Focus sharply on top 5 store margins and holiday staffing alignment."
            autoFocus
          />
        </div>

        <div className="dialog-footer">
          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn-primary btn-sm"
            onClick={onSubmit}
            disabled={isRegenerating || !regeneratePrompt.trim()}
          >
            <Sparkles size={14} />
            <span>{isRegenerating ? "Regenerating..." : "Apply AI Update"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
