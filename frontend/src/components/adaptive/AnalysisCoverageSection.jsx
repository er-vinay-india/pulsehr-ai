import React, { useState } from "react";
import {
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  XCircle,
  AlertOctagon,
  ChevronDown,
  ChevronUp,
  Layers,
  Filter,
} from "lucide-react";

/**
 * AnalysisCoverageSection — Compact Expandable Discovery Audit.
 *
 * Discloses the evaluation status of all 20 decision-focused insight strategies (S01–S20):
 * - Completed: Evaluated with verified semantic bindings and empirical evidence
 * - Needs Inputs: Missing required source fields (documented prerequisites)
 * - Incompatible: Data types, grains, or units fundamentally incompatible
 * - Execution Failure: Strategy threw an execution error during evaluation
 * - Not Implemented: Strategy algorithm not yet implemented in production
 *
 * Styled exclusively using design system SCSS tokens and BEM classes.
 */
export default function AnalysisCoverageSection({ coverage }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");

  if (!coverage || !coverage.strategies) {
    return null;
  }

  const {
    total_strategies = 20,
    completed_count = 0,
    needs_inputs_count = 0,
    incompatible_count = 0,
    execution_failure_count = 0,
    not_implemented_count = 0,
    // Aliases
    supported_count = 0,
    descriptive_only_count = 0,
    strategies = [],
  } = coverage;

  const effectiveCompleted = completed_count || supported_count || 0;

  const filteredStrategies = strategies.filter((s) => {
    if (statusFilter === "all") return true;
    if (statusFilter === "completed") {
      return s.status === "completed" || s.status === "supported";
    }
    return s.status === statusFilter;
  });

  const getStatusBadge = (status, label) => {
    switch (status) {
      case "completed":
      case "supported":
        return (
          <span className="adaptive-coverage-badge adaptive-coverage-badge--completed">
            <CheckCircle2 size={12} />
            {label || "Completed"}
          </span>
        );
      case "needs_inputs":
        return (
          <span className="adaptive-coverage-badge adaptive-coverage-badge--needs_inputs">
            <AlertCircle size={12} />
            {label || "Needs Inputs"}
          </span>
        );
      case "incompatible":
        return (
          <span className="adaptive-coverage-badge adaptive-coverage-badge--incompatible">
            <XCircle size={12} />
            {label || "Incompatible"}
          </span>
        );
      case "execution_failure":
        return (
          <span className="adaptive-coverage-badge adaptive-coverage-badge--execution_failure">
            <AlertOctagon size={12} />
            {label || "Execution Failure"}
          </span>
        );
      case "not_implemented":
      case "descriptive_only":
      default:
        return (
          <span className="adaptive-coverage-badge adaptive-coverage-badge--not_implemented">
            <HelpCircle size={12} />
            {label || "Not Implemented"}
          </span>
        );
    }
  };

  return (
    <div className="adaptive-coverage-drawer">
      {/* Header Summary / Toggle Row */}
      <div className="adaptive-coverage-drawer__header">
        <div className="adaptive-coverage-drawer__lead">
          <div className="adaptive-coverage-drawer__icon">
            <Layers size={18} />
          </div>
          <div className="adaptive-coverage-drawer__title-block">
            <h3 className="adaptive-coverage-drawer__title">
              Strategy Coverage & Audit Screening
            </h3>
            <p className="adaptive-coverage-drawer__subtitle">
              {total_strategies} decision-focused strategies evaluated against uploaded dataset
            </p>
          </div>
        </div>

        {/* Counter Pills & Expand Toggle */}
        <div className="adaptive-coverage-drawer__counters">
          <span className="adaptive-coverage-badge adaptive-coverage-badge--completed">
            <CheckCircle2 size={12} />
            {effectiveCompleted} Completed
          </span>

          <span className="adaptive-coverage-badge adaptive-coverage-badge--needs_inputs">
            <AlertCircle size={12} />
            {needs_inputs_count} Needs Inputs
          </span>

          {incompatible_count > 0 && (
            <span className="adaptive-coverage-badge adaptive-coverage-badge--incompatible">
              <XCircle size={12} />
              {incompatible_count} Incompatible
            </span>
          )}

          {execution_failure_count > 0 && (
            <span className="adaptive-coverage-badge adaptive-coverage-badge--execution_failure">
              <AlertOctagon size={12} />
              {execution_failure_count} Failed
            </span>
          )}

          {not_implemented_count > 0 && (
            <span className="adaptive-coverage-badge adaptive-coverage-badge--not_implemented">
              <HelpCircle size={12} />
              {not_implemented_count} Not Implemented
            </span>
          )}

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="adaptive-priority-btn"
            aria-expanded={isExpanded}
            aria-label="Toggle full strategy coverage details"
          >
            {isExpanded ? "Collapse Coverage" : "View S01–S20 Audit"}
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* Expanded Strategy Grid */}
      {isExpanded && (
        <div className="adaptive-coverage-drawer__content">
          {/* Filter Pills */}
          <div className="adaptive-coverage-filters">
            <span className="adaptive-coverage-filters__label">
              <Filter size={12} /> Filter:
            </span>
            {[
              { id: "all", label: `All (${total_strategies})` },
              { id: "completed", label: `Completed (${effectiveCompleted})` },
              { id: "needs_inputs", label: `Needs Inputs (${needs_inputs_count})` },
              ...(incompatible_count > 0 ? [{ id: "incompatible", label: `Incompatible (${incompatible_count})` }] : []),
              ...(execution_failure_count > 0 ? [{ id: "execution_failure", label: `Failed (${execution_failure_count})` }] : []),
              ...(not_implemented_count > 0 ? [{ id: "not_implemented", label: `Not Implemented (${not_implemented_count})` }] : []),
            ].map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setStatusFilter(f.id)}
                className={`adaptive-coverage-filter-btn ${statusFilter === f.id ? "adaptive-coverage-filter-btn--active" : ""}`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Strategy Items List */}
          <div className="adaptive-coverage-grid">
            {filteredStrategies.map((s) => (
              <div
                key={s.strategy_code}
                className="adaptive-coverage-card"
              >
                <div className="adaptive-coverage-card__header">
                  <div className="adaptive-coverage-card__name-group">
                    <span className="adaptive-coverage-card__code">{s.strategy_code}</span>
                    <span className="adaptive-coverage-card__name">{s.strategy_name}</span>
                  </div>
                  {getStatusBadge(s.status, s.status_label)}
                </div>

                <p className="adaptive-coverage-card__reason">
                  {s.summary_reason}
                </p>

                {s.missing_prerequisites && s.missing_prerequisites.length > 0 && (
                  <div className="adaptive-coverage-card__missing">
                    <strong>Missing Inputs: </strong>
                    {s.missing_prerequisites.join("; ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
