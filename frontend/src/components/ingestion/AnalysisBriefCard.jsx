import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Target,
  HelpCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Edit3,
  ArrowRight,
  Plus,
  Trash2
} from "lucide-react";
import { submitDatasetBrief, getDatasetBrief } from "../../api/client";

export default function AnalysisBriefCard({ uploadResult }) {
  if (!uploadResult || !uploadResult.dataset_id) return null;

  const datasetId = uploadResult.dataset_id;
  const availableCols = uploadResult.columns || [];

  const [objectiveText, setObjectiveText] = useState("");
  const [loading, setLoading] = useState(false);
  const [savedContext, setSavedContext] = useState(null);
  const [isEditing, setIsEditing] = useState(true);
  const [skipped, setSkipped] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [rules, setRules] = useState([]);
  const [error, setError] = useState(null);

  // Load existing brief if already submitted
  useEffect(() => {
    let isMounted = true;
    async function fetchBrief() {
      try {
        const brief = await getDatasetBrief(datasetId);
        if (isMounted && brief && (brief.mode === "INTENT_DRIVEN" || brief.mode === "USER_DIRECTED")) {
          setSavedContext(brief);
          setObjectiveText(brief.user_objective || "");
          setIsEditing(false);
        }
      } catch {
        // No existing brief or failure; keep in default state
      }
    }
    fetchBrief();
    return () => {
      isMounted = false;
    };
  }, [datasetId]);

  const handleAddRule = () => {
    setRules((prev) => [
      ...prev,
      {
        metric_name: availableCols[0] || "",
        operator: ">=",
        target_value: "3",
        unit: ""
      }
    ]);
  };

  const handleRemoveRule = (index) => {
    setRules((prev) => prev.filter((_, i) => i !== index));
  };

  const handleRuleChange = (index, field, value) => {
    setRules((prev) =>
      prev.map((r, i) => (i === index ? { ...r, [field]: value } : r))
    );
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        user_objective: objectiveText.trim(),
        business_rules: rules
          .filter((r) => r.metric_name && r.target_value)
          .map((r) => ({
            metric_name: r.metric_name,
            operator: r.operator,
            target_value: parseFloat(r.target_value) || r.target_value,
            unit: r.unit || ""
          }))
      };

      const result = await submitDatasetBrief(datasetId, payload);
      setSavedContext(result);
      setIsEditing(false);
      setSkipped(false);
    } catch (err) {
      setError(err.message || "Failed to submit analysis brief");
    } finally {
      setLoading(false);
    }
  };

  const handleSkip = async () => {
    setLoading(true);
    setError(null);
    try {
      // Submit empty objective to reset/ensure discovery mode
      const result = await submitDatasetBrief(datasetId, { user_objective: "" });
      setSavedContext(result);
      setSkipped(true);
      setIsEditing(false);
    } catch (err) {
      setError(err.message || "Failed to proceed in discovery mode");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        marginTop: "1.25rem",
        padding: "1.2rem",
        background: "rgba(22, 18, 16, 0.75)",
        border: "1px solid var(--border)",
        borderRadius: "10px",
        boxShadow: "0 4px 14px rgba(0, 0, 0, 0.25)"
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.85rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Sparkles size={18} color="var(--brand-400)" />
          <h4 style={{ margin: 0, fontSize: "1rem", color: "var(--fg-primary)", fontWeight: 700 }}>
            Analysis Brief & Business Context
          </h4>
          <span
            style={{
              fontSize: "0.7rem",
              padding: "2px 8px",
              borderRadius: "12px",
              background: (savedContext?.mode === "INTENT_DRIVEN" || savedContext?.mode === "USER_DIRECTED") ? "rgba(46, 213, 115, 0.15)" : "rgba(255, 255, 255, 0.08)",
              color: (savedContext?.mode === "INTENT_DRIVEN" || savedContext?.mode === "USER_DIRECTED") ? "var(--emerald-tier)" : "var(--fg-muted)",
              border: `1px solid ${(savedContext?.mode === "INTENT_DRIVEN" || savedContext?.mode === "USER_DIRECTED") ? "rgba(46, 213, 115, 0.3)" : "rgba(255, 255, 255, 0.1)"}`
            }}
          >
            {(savedContext?.mode === "INTENT_DRIVEN" || savedContext?.mode === "USER_DIRECTED") ? "USER DIRECTED" : "DISCOVERY MODE"}
          </span>
        </div>

        {!isEditing && (
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            className="btn-secondary"
            style={{
              padding: "4px 10px",
              fontSize: "0.78rem",
              display: "inline-flex",
              alignItems: "center",
              gap: "4px"
            }}
          >
            <Edit3 size={13} />
            <span>Edit Brief</span>
          </button>
        )}
      </div>

      {/* Editing State: Input Form */}
      {isEditing ? (
        <form onSubmit={handleSubmit}>
          <p style={{ fontSize: "0.83rem", color: "var(--fg-secondary)", marginTop: 0, marginBottom: "0.75rem", lineHeight: 1.45 }}>
            Describe what you want this analysis to answer, any corporate targets or rules, and what matters most.
            If skipped, the system will explore and identify patterns automatically.
          </p>

          <div style={{ marginBottom: "0.75rem" }}>
            <textarea
              rows={3}
              value={objectiveText}
              onChange={(e) => setObjectiveText(e.target.value)}
              placeholder="e.g. Employees must work from office at least 3 days per week. Compare departments by compliance and identify departments with unusually high leave rate."
              style={{
                width: "100%",
                background: "rgba(0, 0, 0, 0.35)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "8px",
                padding: "0.75rem",
                color: "var(--fg-primary)",
                fontSize: "0.85rem",
                lineHeight: 1.5,
                resize: "vertical",
                boxSizing: "border-box"
              }}
            />
          </div>

          {/* Advanced / Structured Rules Toggle */}
          <div style={{ marginBottom: "0.85rem" }}>
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              style={{
                background: "none",
                border: "none",
                color: "var(--brand-400)",
                fontSize: "0.78rem",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                padding: 0
              }}
            >
              {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              <span>{showAdvanced ? "Hide explicit targets / rules" : "+ Add explicit compliance rule or target"}</span>
            </button>

            {showAdvanced && (
              <div
                style={{
                  marginTop: "0.6rem",
                  padding: "0.75rem",
                  background: "rgba(0, 0, 0, 0.25)",
                  borderRadius: "6px",
                  border: "1px solid var(--border-subtle)"
                }}
              >
                <div style={{ fontSize: "0.75rem", color: "var(--fg-muted)", marginBottom: "0.5rem" }}>
                  Define specific numeric thresholds to benchmark against (e.g. Minimum 3 WFO days):
                </div>

                {rules.map((rule, idx) => (
                  <div key={idx} style={{ display: "flex", gap: "6px", alignItems: "center", marginBottom: "6px" }}>
                    <select
                      value={rule.metric_name}
                      onChange={(e) => handleRuleChange(idx, "metric_name", e.target.value)}
                      style={{
                        background: "#181412",
                        color: "var(--fg-primary)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "4px",
                        padding: "4px 8px",
                        fontSize: "0.8rem",
                        flex: 2
                      }}
                    >
                      <option value="">Select column...</option>
                      {availableCols.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>

                    <select
                      value={rule.operator}
                      onChange={(e) => handleRuleChange(idx, "operator", e.target.value)}
                      style={{
                        background: "#181412",
                        color: "var(--fg-primary)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "4px",
                        padding: "4px 8px",
                        fontSize: "0.8rem",
                        flex: 1
                      }}
                    >
                      <option value=">=">&gt;= (Min)</option>
                      <option value="<=">&lt;= (Max)</option>
                      <option value="==">== (Exact)</option>
                      <option value=">">&gt; (Greater)</option>
                      <option value="<">&lt; (Less)</option>
                    </select>

                    <input
                      type="text"
                      placeholder="Target value"
                      value={rule.target_value}
                      onChange={(e) => handleRuleChange(idx, "target_value", e.target.value)}
                      style={{
                        background: "#181412",
                        color: "var(--fg-primary)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "4px",
                        padding: "4px 8px",
                        fontSize: "0.8rem",
                        flex: 1
                      }}
                    />

                    <button
                      type="button"
                      onClick={() => handleRemoveRule(idx)}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--ruby-tier)",
                        cursor: "pointer",
                        padding: "4px"
                      }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}

                <button
                  type="button"
                  onClick={handleAddRule}
                  style={{
                    background: "none",
                    border: "1px dashed var(--border-subtle)",
                    color: "var(--fg-secondary)",
                    borderRadius: "4px",
                    padding: "4px 10px",
                    fontSize: "0.75rem",
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "4px",
                    marginTop: "4px"
                  }}
                >
                  <Plus size={12} /> Add Rule
                </button>
              </div>
            )}
          </div>

          {error && (
            <div style={{ color: "var(--ruby-tier)", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
              {error}
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary"
              style={{
                fontSize: "0.82rem",
                padding: "0.45rem 1rem",
                cursor: loading ? "wait" : "pointer"
              }}
            >
              <Target size={14} style={{ marginRight: "6px" }} />
              <span>{loading ? "Analyzing Intent..." : "Save Analysis Brief & Analyze"}</span>
            </button>

            <button
              type="button"
              disabled={loading}
              onClick={handleSkip}
              className="btn-secondary"
              style={{
                fontSize: "0.82rem",
                padding: "0.45rem 0.9rem",
                cursor: loading ? "wait" : "pointer",
                color: "var(--fg-secondary)"
              }}
            >
              Skip and explore automatically
            </button>
          </div>
        </form>
      ) : (
        /* Saved / Reconciled Context Display */
        <div>
          {skipped ? (
            <div style={{ fontSize: "0.85rem", color: "var(--fg-secondary)", display: "flex", alignItems: "center", gap: "6px" }}>
              <CheckCircle2 size={16} color="var(--brand-400)" />
              <span>Automatic discovery mode active. The pipeline is exploring patterns and opportunities without user-imposed constraints.</span>
            </div>
          ) : (
            <div>
              {savedContext?.user_objective && (
                <div style={{ marginBottom: "0.6rem" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--fg-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    User Objective:
                  </span>
                  <div style={{ fontSize: "0.88rem", color: "var(--fg-primary)", marginTop: "2px", fontWeight: 500 }}>
                    &ldquo;{savedContext.user_objective}&rdquo;
                  </div>
                </div>
              )}

              {/* Identified Rules */}
              {savedContext?.business_rules && savedContext.business_rules.length > 0 && (
                <div style={{ marginTop: "0.6rem" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--fg-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    Verified Business Rules (Prioritized in Pipeline):
                  </span>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "4px" }}>
                    {savedContext.business_rules.map((rule, idx) => (
                      <span
                        key={idx}
                        style={{
                          fontSize: "0.78rem",
                          padding: "3px 8px",
                          borderRadius: "4px",
                          background: "rgba(224, 86, 36, 0.12)",
                          color: "var(--brand-400)",
                          border: "1px solid rgba(224, 86, 36, 0.25)",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "4px"
                        }}
                      >
                        <strong>{rule.metric_name}</strong> {rule.operator} {rule.target_value}
                        <span style={{ fontSize: "0.65rem", opacity: 0.8 }}>[{rule.source}]</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Priority Questions */}
              {savedContext?.questions_to_answer && savedContext.questions_to_answer.length > 0 && (
                <div style={{ marginTop: "0.6rem" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--fg-muted)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    Priority Questions:
                  </span>
                  <ul style={{ margin: "4px 0 0 1rem", padding: 0, fontSize: "0.82rem", color: "var(--fg-secondary)" }}>
                    {savedContext.questions_to_answer.map((q, idx) => (
                      <li key={idx} style={{ marginBottom: "2px" }}>{q}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Unsupported Requests if any */}
              {savedContext?.unsupported_requests && savedContext.unsupported_requests.length > 0 && (
                <div style={{ marginTop: "0.6rem", padding: "6px 10px", borderRadius: "6px", background: "rgba(255, 170, 0, 0.08)", border: "1px solid rgba(255, 170, 0, 0.2)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", color: "#ffaa00", fontSize: "0.78rem" }}>
                    <AlertTriangle size={14} />
                    <strong>Note on unsupported requests:</strong>
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--fg-secondary)", marginTop: "2px" }}>
                    {savedContext.unsupported_requests.join("; ")} (skipped without assumption).
                  </div>
                </div>
              )}

              <div style={{ marginTop: "0.85rem", display: "flex", alignItems: "center", gap: "8px" }}>
                <a
                  href="#overview"
                  className="btn-primary"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    textDecoration: "none",
                    fontSize: "0.8rem",
                    padding: "0.35rem 0.85rem"
                  }}
                >
                  <span>View Executive Report</span>
                  <ArrowRight size={14} />
                </a>
                <span style={{ fontSize: "0.75rem", color: "var(--fg-muted)" }}>
                  Context applied to Executive Overview, Slides, and Copilot.
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
