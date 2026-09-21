import React from "react";
import {
  Layers,
  Link2,
  CheckSquare,
  Database,
  CheckCircle2,
  ShieldCheck,
  RotateCw,
  Calendar,
  AlertTriangle,
  Info,
  Sparkles
} from "lucide-react";

export default function DeckConfigView({
  themes,
  selectedThemeId,
  setSelectedThemeId,
  sheets,
  scopeType,
  setScopeType,
  selectedGroupId,
  setSelectedGroupId,
  customSheetIds,
  setCustomSheetIds,
  selectedSheetId,
  setSelectedSheetId,
  objective,
  setObjective,
  audience,
  setAudience,
  targetLength,
  setTargetLength,
  deckStyle,
  setDeckStyle,
  instructions,
  setInstructions,
  autoDownload,
  setAutoDownload,
  scopePreview,
  isLoadingPreview,
  jobError,
  onStartGeneration
}) {
  return (
    <div className="pres-config-body">
      <div className="config-form-grid">
        {/* Left Column: Scope & Core Parameters */}
        <div className="config-col">
          {/* PRESENTATION SCOPE SELECTION */}
          <div className="form-group">
            <label className="section-label">Presentation Scope</label>
            <div className="scope-selection-grid">
              {[
                {
                  id: "workspace",
                  title: "Executive Workspace Summary",
                  desc: "All eligible datasets & validated relationships",
                  icon: Layers
                },
                {
                  id: "connected_group",
                  title: "Selected Connected Group",
                  desc: "Related sheets linked by validated keys",
                  icon: Link2
                },
                {
                  id: "custom_sheets",
                  title: "Selected Sheets",
                  desc: "Custom multi-sheet comparison",
                  icon: CheckSquare
                },
                {
                  id: "single_sheet",
                  title: "Single Sheet",
                  desc: "Focused deep dive on one dataset",
                  icon: Database
                }
              ].map(opt => {
                const isSelected = scopeType === opt.id;
                const IconComp = opt.icon;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    className={`scope-option-card ${isSelected ? "selected" : ""}`}
                    onClick={() => setScopeType(opt.id)}
                  >
                    <div className="scope-card-top">
                      <IconComp size={15} className="scope-icon" />
                      <span className="scope-title">{opt.title}</span>
                      {isSelected && <CheckCircle2 size={14} className="scope-check" />}
                    </div>
                    <span className="scope-desc">{opt.desc}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* SCOPE-DEPENDENT DATASET PICKERS */}
          {scopeType === "single_sheet" && (
            <div className="form-group">
              <label htmlFor="pres-sheet">Source Dataset / Sheet</label>
              <select
                id="pres-sheet"
                className="form-select"
                value={selectedSheetId}
                onChange={e => setSelectedSheetId(e.target.value)}
              >
                {sheets.map(s => (
                  <option key={s.id} value={s.id}>
                    {s.display_name || s.name} ({s.row_count.toLocaleString()} rows)
                  </option>
                ))}
              </select>
            </div>
          )}

          {scopeType === "connected_group" && (
            <div className="form-group">
              <label htmlFor="pres-group">Select Connected Group</label>
              {scopePreview?.connected_groups && scopePreview.connected_groups.length > 0 ? (
                <select
                  id="pres-group"
                  className="form-select"
                  value={selectedGroupId}
                  onChange={e => setSelectedGroupId(e.target.value)}
                >
                  {scopePreview.connected_groups.map(g => (
                    <option key={g.group_id} value={g.group_id}>
                      Group {g.group_id + 1}: {g.sheet_names.join(" + ")} ({g.total_rows.toLocaleString()} rows)
                    </option>
                  ))}
                </select>
              ) : (
                <div className="empty-group-note">
                  <span>No multi-sheet relationships detected. Evaluated within individual group boundaries.</span>
                </div>
              )}
            </div>
          )}

          {scopeType === "custom_sheets" && (
            <div className="form-group">
              <label>Choose Sheets to Include ({customSheetIds.length} of {sheets.length} selected)</label>
              <div className="custom-sheets-checklist">
                {sheets.map(s => {
                  const isChecked = customSheetIds.includes(String(s.id));
                  return (
                    <label key={s.id} className={`sheet-checkbox-row ${isChecked ? "checked" : ""}`}>
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={e => {
                          if (e.target.checked) {
                            setCustomSheetIds([...customSheetIds, String(s.id)]);
                          } else {
                            setCustomSheetIds(customSheetIds.filter(id => id !== String(s.id)));
                          }
                        }}
                      />
                      <span className="sheet-check-name">{s.display_name || s.name}</span>
                      <span className="sheet-check-rows">{s.row_count.toLocaleString()} rows</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {/* LIVE PREFLIGHT AUDIT CARD */}
          <div className="preflight-summary-card">
            <div className="preflight-header">
              <div className="preflight-title">
                <ShieldCheck size={14} style={{ color: "#8ef0c8" }} />
                <span>Preflight Scope &amp; Integrity Audit</span>
              </div>
              {isLoadingPreview ? (
                <span className="preflight-status loading">
                  <RotateCw size={11} className="spin-icon" /> Auditing...
                </span>
              ) : (
                <span className="preflight-status ready">Verified Scope</span>
              )}
            </div>

            {scopePreview ? (
              <div className="preflight-details-stack">
                <div className="preflight-row">
                  <span className="preflight-lbl">
                    <Database size={12} /> Sources:
                  </span>
                  <span className="preflight-val">
                    {scopePreview.included_sheets?.length || 0} sheets ({(scopePreview.total_records ?? scopePreview.included_sheets?.reduce((sum, sheet) => sum + Number(sheet.row_count || 0), 0) ?? 0).toLocaleString()} rows)
                  </span>
                </div>

                <div className="preflight-row">
                  <span className="preflight-lbl">
                    <Calendar size={12} /> Period:
                  </span>
                  <span className="preflight-val">
                    {scopePreview.reporting_period_summary || "Period not established"}
                  </span>
                </div>

                {scopePreview.is_partial_year && (
                  <div className="preflight-warning-pill">
                    <AlertTriangle size={12} />
                    <span>Partial Year Disclosure Active (&lt; 330 days in cycle)</span>
                  </div>
                )}

                <div className="preflight-row">
                  <span className="preflight-lbl">
                    <Link2 size={12} /> Relationships:
                  </span>
                  <span className="preflight-val">
                    {scopePreview.validated_relationships?.length || 0} validated links ({scopePreview.relationship_coverage_pct ?? 0}% coverage)
                  </span>
                </div>

                {scopePreview.disconnected_boundary_note && (
                  <div className="preflight-boundary-note">
                    <Info size={12} />
                    <span>{scopePreview.disconnected_boundary_note}</span>
                  </div>
                )}

                {scopePreview.exclusions && scopePreview.exclusions.length > 0 && (
                  <div className="preflight-exclusions">
                    <span className="exclusions-lbl">Excluded:</span>
                    <span className="exclusions-val">
                      {scopePreview.exclusions.map(ex => `${ex.name} (${ex.reason})`).join("; ")}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div className="preflight-skeleton">Evaluating workspace datasets and relational coverage...</div>
            )}
          </div>

          <div className="form-group">
            <label htmlFor="pres-obj">Presentation Objective / Topic</label>
            <input
              id="pres-obj"
              type="text"
              className="form-input"
              value={objective}
              onChange={e => setObjective(e.target.value)}
              placeholder="e.g. Executive Operations & Performance Review"
            />
            <div className="quick-suggestions">
              <button
                type="button"
                className="suggestion-tag"
                onClick={() => setObjective("Consolidated Executive Operations & Performance Review")}
              >
                Consolidated Executive
              </button>
              <button
                type="button"
                className="suggestion-tag"
                onClick={() => setObjective("Executive Store Revenue & Seasonal Sales Variance")}
              >
                Sales Variance
              </button>
              <button
                type="button"
                className="suggestion-tag"
                onClick={() => setObjective("Strategic Workforce Distribution & Attendance Review")}
              >
                Workforce Plan
              </button>
            </div>
          </div>

          <div className="form-row-2">
            <div className="form-group">
              <label htmlFor="pres-aud">Target Audience</label>
              <select
                id="pres-aud"
                className="form-select"
                value={audience}
                onChange={e => setAudience(e.target.value)}
              >
                <option value="C-Suite & Operations Leadership">C-Suite & Operations Leadership</option>
                <option value="Regional Store & Field Directors">Regional Store & Field Directors</option>
                <option value="Workforce Planning & People Ops">Workforce Planning & People Ops</option>
                <option value="Board of Directors & Investors">Board of Directors & Investors</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="pres-style">Presentation format</label>
              <select id="pres-style" className="form-select" value={deckStyle} onChange={e => setDeckStyle(e.target.value)}>
                <option value="decision_brief">Decision brief · same findings as the overview</option>
                <option value="standard">Detailed analytical presentation</option>
              </select>
              {deckStyle === 'decision_brief' && <p className="hint-text">Includes supported findings, editable comparisons and coverage notes. Slide count follows the evidence.</p>}
            </div>
            {deckStyle === 'standard' && <div className="form-group">
              <label htmlFor="pres-len">Target Slide Count</label>
              <select
                id="pres-len"
                className="form-select"
                value={targetLength}
                onChange={e => setTargetLength(e.target.value)}
              >
                <option value="4">4 Slides (Executive Summary)</option>
                <option value="6">6 Slides (Standard Briefing)</option>
                <option value="8">8 Slides (Comprehensive Review)</option>
                <option value="10">10 Slides (Detailed Deep Dive)</option>
              </select>
            </div>}
          </div>

          <div className="form-group">
            <label htmlFor="pres-instr">{deckStyle === 'decision_brief' ? 'Presenter notes (do not change verified findings)' : 'Additional Focus & Instructions (Optional)'}</label>
            <textarea
              id="pres-instr"
              className="form-textarea"
              rows={3}
              value={instructions}
              onChange={e => setInstructions(e.target.value)}
              placeholder="e.g. Focus on holiday promotional lift and inventory replenishment cycles."
            />
          </div>

          <div className="form-group" style={{ marginTop: "10px" }}>
            <label style={{ display: "inline-flex", alignItems: "center", gap: "8px", cursor: "pointer", fontSize: "0.82rem", color: "var(--fg-primary)", userSelect: "none" }}>
              <input
                type="checkbox"
                checked={autoDownload}
                onChange={e => setAutoDownload(e.target.checked)}
                style={{ width: "16px", height: "16px", cursor: "pointer", accentColor: "var(--brand-400)" }}
              />
              <span>Automatically download PowerPoint (.pptx) file when ready</span>
            </label>
          </div>
        </div>

        {/* Right Column: Visual Theme Selection */}
        <div className="config-col">
          <label className="section-label">Select Visual Presentation Theme</label>
          <div className="themes-card-grid">
            {themes.map(t => {
              const isSelected = t.id === selectedThemeId;
              return (
                <div
                  key={t.id}
                  className={`theme-card ${isSelected ? "selected" : ""}`}
                  style={{ backgroundColor: t.card_bg, borderColor: isSelected ? t.brand_color : t.card_border }}
                  onClick={() => setSelectedThemeId(t.id)}
                >
                  <div className="theme-card-top">
                    <span className="theme-name" style={{ color: t.primary_text }}>{t.name}</span>
                    {isSelected && <CheckCircle2 size={16} style={{ color: t.brand_color }} />}
                  </div>

                  {/* Theme Swatches Preview */}
                  <div className="theme-swatch-row">
                    <span className="swatch" style={{ backgroundColor: t.bg_color }} title="Background" />
                    <span className="swatch" style={{ backgroundColor: t.brand_color }} title="Brand" />
                    <span className="swatch" style={{ backgroundColor: t.accent_color }} title="Accent" />
                    <span className="swatch" style={{ backgroundColor: t.success_color }} title="Success" />
                  </div>

                  <div className="theme-preview-box" style={{ backgroundColor: t.bg_color }}>
                    <span className="mini-title" style={{ color: t.brand_color }}>Executive Preview</span>
                    <div className="mini-bar-preview">
                      <span style={{ width: "80%", backgroundColor: t.brand_color }} />
                      <span style={{ width: "55%", backgroundColor: t.accent_color }} />
                      <span style={{ width: "35%", backgroundColor: t.success_color }} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {jobError && (
            <div className="pres-error-callout">
              <AlertTriangle size={16} />
              <span>{jobError}</span>
            </div>
          )}
        </div>
      </div>

      <div className="pres-config-footer">
        <div className="footer-left-note">
          <CheckCircle2 size={14} />
          <span>Deterministic SQL ground truth · Native OpenXML PowerPoint charts</span>
        </div>
        <button
          type="button"
          className="btn-primary btn-lg"
          onClick={onStartGeneration}
        >
          <Sparkles size={18} />
          <span>Generate Presentation</span>
        </button>
      </div>
    </div>
  );
}
