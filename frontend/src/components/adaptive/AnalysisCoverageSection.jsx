import React, { useState, useMemo } from "react";
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
  Search,
  Sparkles,
  ShieldCheck,
  Users,
  Target,
  DollarSign,
  ArrowRight,
  TrendingUp,
  Briefcase,
  SlidersHorizontal,
} from "lucide-react";

/**
 * HR Functional Pillars mapping for S01–S20 Decision Strategies.
 */
const HR_PILLARS = {
  all: {
    id: "all",
    label: "All HR Playbooks",
    icon: Layers,
    color: "#ff8a62",
  },
  workforce: {
    id: "workforce",
    label: "Workforce & Operations",
    icon: Users,
    color: "#ff8a62",
    description: "Shift attendance, scheduled obligations, staffing capacity, and operational footprint.",
  },
  talent: {
    id: "talent",
    label: "Talent, Retention & Cohorts",
    icon: Target,
    color: "#38bdf8",
    description: "Tenure dynamics, cohort attrition risk, recurring performance dips, and target adherence.",
  },
  economics: {
    id: "economics",
    label: "Compensation & Economics",
    icon: DollarSign,
    color: "#34d399",
    description: "Payroll variance, overtime leakage, tail concentration, and unit labor productivity.",
  },
  governance: {
    id: "governance",
    label: "HR Governance & Simpson's Guardrails",
    icon: ShieldCheck,
    color: "#c084fc",
    description: "Subgroup bias detection, Simpson's Paradox reversal checks, SLA aging, and predictive defensibility.",
  },
};

/**
 * Detailed HR Executive Decision Questions and Context for S01–S20.
 */
const STRATEGY_HR_METADATA = {
  S01: {
    pillar: "workforce",
    question: "Are duty rosters and shift obligations being met without unexcused coverage voids?",
    executiveImpact: "Highlights operational understaffing and unfulfilled shifts across operating units.",
  },
  S02: {
    pillar: "talent",
    question: "Are absenteeism spikes and productivity drops recurring chronically among specific groups?",
    executiveImpact: "Separates one-off episodic events from structural burnout and disengagement patterns.",
  },
  S03: {
    pillar: "workforce",
    question: "Do attendance shortfalls cluster on specific days of the week, shifts, or around holidays?",
    executiveImpact: "Exposes weekend/Monday surge absences and holiday scheduling vulnerabilities.",
  },
  S04: {
    pillar: "governance",
    question: "Are observed department shifts statistically meaningful or merely expected operational noise?",
    executiveImpact: "Prevents executive overreaction to small sample fluctuations and normal variance.",
  },
  S05: {
    pillar: "talent",
    question: "Which business units are systematically falling short of organizational target commitments?",
    executiveImpact: "Surfaces chronic SLA misses and lagging store teams before quarterly close.",
  },
  S06: {
    pillar: "talent",
    question: "Where are employees dropping out in the talent progression and onboarding pipeline?",
    executiveImpact: "Identifies early-tenure leakage and friction points in internal promotion ladders.",
  },
  S07: {
    pillar: "governance",
    question: "Are employee requests, grievances, or staffing backlogs aging past standard policy SLAs?",
    executiveImpact: "Guards against compliance risk and unaddressed employee relations backlog.",
  },
  S08: {
    pillar: "workforce",
    question: "Which specific facilities, roles, or absence types drive the bulk of total lost hours?",
    executiveImpact: "Focuses intervention on the 20% of operational drivers causing 80% of workforce impact.",
  },
  S09: {
    pillar: "talent",
    question: "How do comparable peer stores or facilities differ in performance and labor efficiency?",
    executiveImpact: "Benchmarks peer units of equivalent scale to uncover localized operational divergence.",
  },
  S10: {
    pillar: "governance",
    question: "Does company-wide aggregate progress mask critical underlying disparities within subgroups?",
    executiveImpact: "Simpson's Paradox detector: protects leadership from false-positive company-wide trends.",
  },
  S11: {
    pillar: "economics",
    question: "Which specific business units or departments are the primary engines of total cost variance?",
    executiveImpact: "Pins down root-cause departments driving payroll budget expansion.",
  },
  S12: {
    pillar: "economics",
    question: "Is overtime burden heavily concentrated in an isolated tail of overburdened employees?",
    executiveImpact: "Surfaces acute burnout and fatigue exposure within specialized critical staff.",
  },
  S13: {
    pillar: "talent",
    question: "How do distinct hire cohorts retain and ramp over time compared to historical baselines?",
    executiveImpact: "Tracks 30/60/90-day retention curves across seasonal and quarterly onboarding cohorts.",
  },
  S14: {
    pillar: "workforce",
    question: "Is frontline staffing capacity dynamically matched to actual customer and foot-traffic demand?",
    executiveImpact: "Quantifies over-scheduling during slow periods and under-scheduling during peak demand.",
  },
  S15: {
    pillar: "economics",
    question: "What is the net economic return and revenue yield generated per paid employee hour?",
    executiveImpact: "Connects human capital investments directly to store-level bottom-line profitability.",
  },
  S16: {
    pillar: "governance",
    question: "Are there non-obvious cross-correlations between overtime, tenure, and error/incident rates?",
    executiveImpact: "Discovers hidden interactions (e.g. high overtime correlating with compliance lapses).",
  },
  S17: {
    pillar: "workforce",
    question: "Do physical timecard punches accurately reconcile with master payroll and roster ledgers?",
    executiveImpact: "Identifies phantom hours, punch errors, and unverified payroll discrepancies.",
  },
  S18: {
    pillar: "governance",
    question: "What critical employee segments are currently unmonitored due to incomplete telemetry?",
    executiveImpact: "Surfaces data blind spots and unmonitored contract/temporary workforce pools.",
  },
  S19: {
    pillar: "governance",
    question: "What is the defensible forward trajectory for headcount and payroll over the upcoming quarter?",
    executiveImpact: "Delivers statistically bounded workforce forecasts for budgeting and headcount planning.",
  },
  S20: {
    pillar: "economics",
    question: "How sensitive is operational profitability to wage increases, overtime spikes, or turnover?",
    executiveImpact: "Stress-tests human capital budgets against market shocks and regulatory wage shifts.",
  },
};

/**
 * AnalysisCoverageSection — Executive HR Strategy Coverage & Intelligence Audit.
 *
 * Built for HR Executives, People Analytics Leaders, and Chief People Officers:
 * 1. Visual Capability Readiness Health Meter (Active vs. Unlockable vs. Data Gaps).
 * 2. 3 Executive Summary KPI Cards (Operational Live Playbooks, Unlockable Upside, Simpson's Bias Guardrails).
 * 3. 4 Strategic HR Pillars (Workforce Operations, Talent & Retention, Compensation & Economics, Governance & Bias).
 * 4. Actionable Unlock Recipes with direct column prerequisite chips and Explorer navigation.
 * 5. Instant Search and Status Filters.
 */
export default function AnalysisCoverageSection({ coverage, sheetId, onNavigateTab }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [selectedPillar, setSelectedPillar] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

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
    supported_count = 0,
    strategies = [],
  } = coverage;

  const effectiveCompleted = completed_count || supported_count || 0;
  const gapsCount = incompatible_count + execution_failure_count + not_implemented_count;

  // Percentage Calculations for Executive Readiness Meter
  const activePct = Math.round((effectiveCompleted / total_strategies) * 100);
  const unlockablePct = Math.round((needs_inputs_count / total_strategies) * 100);
  const gapsPct = Math.max(0, 100 - activePct - unlockablePct);

  // Filter & Search Logic
  const filteredStrategies = useMemo(() => {
    return strategies.filter((item) => {
      const meta = STRATEGY_HR_METADATA[item.strategy_code] || { pillar: "governance", question: "" };

      // Pillar Filter
      if (selectedPillar !== "all" && meta.pillar !== selectedPillar) {
        return false;
      }

      // Status Filter
      if (statusFilter === "completed") {
        if (item.status !== "completed" && item.status !== "supported") return false;
      } else if (statusFilter === "needs_inputs") {
        if (item.status !== "needs_inputs") return false;
      } else if (statusFilter === "gaps") {
        if (item.status === "completed" || item.status === "supported" || item.status === "needs_inputs") return false;
      }

      // Text Search Query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const codeMatch = item.strategy_code.toLowerCase().includes(query);
        const nameMatch = item.strategy_name.toLowerCase().includes(query);
        const questionMatch = meta.question.toLowerCase().includes(query);
        const reasonMatch = (item.summary_reason || "").toLowerCase().includes(query);
        const missingMatch = (item.missing_prerequisites || []).some((p) => p.toLowerCase().includes(query));

        if (!codeMatch && !nameMatch && !questionMatch && !reasonMatch && !missingMatch) {
          return false;
        }
      }

      return true;
    });
  }, [strategies, selectedPillar, statusFilter, searchQuery]);

  // Pillar counts
  const pillarCounts = useMemo(() => {
    const counts = { all: strategies.length, workforce: 0, talent: 0, economics: 0, governance: 0 };
    strategies.forEach((s) => {
      const meta = STRATEGY_HR_METADATA[s.strategy_code];
      if (meta && counts[meta.pillar] !== undefined) {
        counts[meta.pillar] += 1;
      } else {
        counts.governance += 1;
      }
    });
    return counts;
  }, [strategies]);

  const getStatusBadge = (status, label) => {
    switch (status) {
      case "completed":
      case "supported":
        return (
          <span className="adaptive-coverage-badge adaptive-coverage-badge--completed">
            <CheckCircle2 size={12} />
            {label || "Active Playbook"}
          </span>
        );
      case "needs_inputs":
        return (
          <span className="adaptive-coverage-badge adaptive-coverage-badge--needs_inputs">
            <Sparkles size={12} />
            {label || "Unlockable with Data"}
          </span>
        );
      case "incompatible":
        return (
          <span className="adaptive-coverage-badge adaptive-coverage-badge--incompatible">
            <XCircle size={12} />
            {label || "Schema Incompatible"}
          </span>
        );
      case "execution_failure":
        return (
          <span className="adaptive-coverage-badge adaptive-coverage-badge--execution_failure">
            <AlertOctagon size={12} />
            {label || "Evaluation Error"}
          </span>
        );
      case "not_implemented":
      default:
        return (
          <span className="adaptive-coverage-badge adaptive-coverage-badge--not_implemented">
            <HelpCircle size={12} />
            {label || "Data Schema Gap"}
          </span>
        );
    }
  };

  return (
    <section className="adaptive-coverage-drawer" aria-label="Executive HR Strategy Coverage & Intelligence Audit">
      {/* Executive Header Banner */}
      <div className="adaptive-coverage-drawer__header">
        <div className="adaptive-coverage-drawer__lead">
          <div className="adaptive-coverage-drawer__icon">
            <Briefcase size={20} />
          </div>
          <div className="adaptive-coverage-drawer__title-block">
            <div className="adaptive-coverage-drawer__title-row">
              <h3 className="adaptive-coverage-drawer__title">
                Executive HR Strategy Coverage & Intelligence Audit
              </h3>
              <span className="adaptive-coverage-drawer__version-tag">20-Playbook Suite</span>
            </div>
            <p className="adaptive-coverage-drawer__subtitle">
              Rigorous algorithmic audit across workforce operations, cohort retention, payroll economics, and Simpson&apos;s Paradox guardrails.
            </p>
          </div>
        </div>

        {/* Header Right: Readiness Meter & Expand Action */}
        <div className="adaptive-coverage-drawer__actions">
          <div className="adaptive-coverage-header-meter" title={`Capability Readiness: ${activePct}% Active, ${unlockablePct}% Unlockable, ${gapsPct}% Schema Gaps`}>
            <div className="adaptive-coverage-header-meter__bar">
              <div
                className="adaptive-coverage-header-meter__slice adaptive-coverage-header-meter__slice--active"
                style={{ width: `${activePct}%` }}
              />
              <div
                className="adaptive-coverage-header-meter__slice adaptive-coverage-header-meter__slice--unlockable"
                style={{ width: `${unlockablePct}%` }}
              />
              <div
                className="adaptive-coverage-header-meter__slice adaptive-coverage-header-meter__slice--gaps"
                style={{ width: `${gapsPct}%` }}
              />
            </div>
            <div className="adaptive-coverage-header-meter__labels">
              <span className="adaptive-coverage-header-meter__txt active">
                <CheckCircle2 size={10} /> {effectiveCompleted} Active
              </span>
              <span className="adaptive-coverage-header-meter__txt unlockable">
                <Sparkles size={10} /> {needs_inputs_count} Unlockable
              </span>
              <span className="adaptive-coverage-header-meter__txt gaps">
                {gapsCount} Schema Gaps
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="adaptive-coverage-expand-btn"
            aria-expanded={isExpanded}
            aria-label="Toggle full executive HR strategy audit"
          >
            {isExpanded ? "Collapse HR Audit" : "Review HR Strategy Audit"}
            {isExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
          </button>
        </div>
      </div>

      {/* Expanded Executive Audit Console */}
      {isExpanded && (
        <div className="adaptive-coverage-drawer__content">
          {/* Executive KPI Metric Cards */}
          <div className="adaptive-coverage-kpi-grid">
            <div className="adaptive-coverage-kpi-card adaptive-coverage-kpi-card--active">
              <div className="adaptive-coverage-kpi-card__top">
                <span className="adaptive-coverage-kpi-card__label">Active Capability Coverage</span>
                <span className="adaptive-coverage-kpi-card__pill active">
                  <CheckCircle2 size={11} /> {activePct}% Readiness
                </span>
              </div>
              <div className="adaptive-coverage-kpi-card__stat">
                {effectiveCompleted} <span className="adaptive-coverage-kpi-card__total">/ {total_strategies} Playbooks</span>
              </div>
              <p className="adaptive-coverage-kpi-card__desc">
                Currently powering live board-ready dashboard visualizations, concentration metrics, and empirical evidence packages.
              </p>
            </div>

            <div className="adaptive-coverage-kpi-card adaptive-coverage-kpi-card--unlockable">
              <div className="adaptive-coverage-kpi-card__top">
                <span className="adaptive-coverage-kpi-card__label">Immediate Unlockable Upside</span>
                <span className="adaptive-coverage-kpi-card__pill unlockable">
                  <Sparkles size={11} /> High ROI Opportunity
                </span>
              </div>
              <div className="adaptive-coverage-kpi-card__stat">
                {needs_inputs_count} <span className="adaptive-coverage-kpi-card__total">Strategies Awaiting Fields</span>
              </div>
              <p className="adaptive-coverage-kpi-card__desc">
                Mapping 1–2 optional HR columns (e.g. scheduled duty roster, tenure, or overtime) immediately activates deep cohort and capacity diagnostics.
              </p>
            </div>

            <div className="adaptive-coverage-kpi-card adaptive-coverage-kpi-card--governance">
              <div className="adaptive-coverage-kpi-card__top">
                <span className="adaptive-coverage-kpi-card__label">Audit & Guardrail Integrity</span>
                <span className="adaptive-coverage-kpi-card__pill governance">
                  <ShieldCheck size={11} /> Simpson&apos;s Guard Active
                </span>
              </div>
              <div className="adaptive-coverage-kpi-card__stat">
                100% <span className="adaptive-coverage-kpi-card__total">Evidence Audited</span>
              </div>
              <p className="adaptive-coverage-kpi-card__desc">
                Subgroup composition verified. Strict analytical discipline prevents misleading claims or speculative metrics without source data.
              </p>
            </div>
          </div>

          {/* HR Strategic Pillar Navigation Tabs */}
          <div className="adaptive-coverage-pillar-nav">
            {Object.values(HR_PILLARS).map((pillar) => {
              const Icon = pillar.icon;
              const isActive = selectedPillar === pillar.id;
              const count = pillarCounts[pillar.id] || 0;
              return (
                <button
                  key={pillar.id}
                  type="button"
                  onClick={() => setSelectedPillar(pillar.id)}
                  className={`adaptive-coverage-pillar-btn ${isActive ? "adaptive-coverage-pillar-btn--active" : ""}`}
                >
                  <Icon size={14} style={{ color: pillar.color }} />
                  <span>{pillar.label}</span>
                  <span className="adaptive-coverage-pillar-btn__count">{count}</span>
                </button>
              );
            })}
          </div>

          {/* Secondary Controls: Status Filters & Search Bar */}
          <div className="adaptive-coverage-controls">
            <div className="adaptive-coverage-controls__filters">
              <span className="adaptive-coverage-controls__label">
                <Filter size={12} /> Status:
              </span>
              {[
                { id: "all", label: "All Statuses" },
                { id: "completed", label: `Active (${effectiveCompleted})` },
                { id: "needs_inputs", label: `Unlockable (${needs_inputs_count})` },
                { id: "gaps", label: `Schema Gaps (${gapsCount})` },
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

            <div className="adaptive-coverage-search">
              <Search size={14} className="adaptive-coverage-search__icon" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search playbooks, HR questions, or missing fields..."
                className="adaptive-coverage-search__input"
                aria-label="Search HR strategy playbooks"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="adaptive-coverage-search__clear"
                  aria-label="Clear search input"
                >
                  ×
                </button>
              )}
            </div>
          </div>

          {/* Strategy Cards Grid */}
          <div className="adaptive-coverage-grid">
            {filteredStrategies.length === 0 ? (
              <div className="adaptive-coverage-empty">
                <p>No strategy playbooks match the selected filters or search query.</p>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedPillar("all");
                    setStatusFilter("all");
                    setSearchQuery("");
                  }}
                  className="adaptive-priority-btn"
                >
                  Reset Filters
                </button>
              </div>
            ) : (
              filteredStrategies.map((s) => {
                const meta = STRATEGY_HR_METADATA[s.strategy_code] || {
                  pillar: "governance",
                  question: "Does the current dataset provide statistically sound evidence for this decision domain?",
                  executiveImpact: "Enforces evidence validation rules.",
                };
                const pillarDef = HR_PILLARS[meta.pillar] || HR_PILLARS.governance;
                const isCompleted = s.status === "completed" || s.status === "supported";
                const isNeedsInputs = s.status === "needs_inputs";

                return (
                  <article
                    key={s.strategy_code}
                    className={`adaptive-coverage-card adaptive-coverage-card--${s.status}`}
                  >
                    <div className="adaptive-coverage-card__header">
                      <div className="adaptive-coverage-card__name-block">
                        <div className="adaptive-coverage-card__top-meta">
                          <span className="adaptive-coverage-card__code">{s.strategy_code}</span>
                          <span
                            className="adaptive-coverage-card__pillar-badge"
                            style={{ color: pillarDef.color, borderColor: `${pillarDef.color}40`, background: `${pillarDef.color}15` }}
                          >
                            {pillarDef.label.split("&")[0].trim()}
                          </span>
                        </div>
                        <h4 className="adaptive-coverage-card__title">{s.strategy_name}</h4>
                      </div>
                      <div className="adaptive-coverage-card__badge-wrap">
                        {getStatusBadge(s.status, s.status_label)}
                      </div>
                    </div>

                    {/* HR Decision Focus Box */}
                    <div className="adaptive-coverage-card__question-box">
                      <span className="adaptive-coverage-card__question-tag">HR Decision Focus:</span>
                      <p className="adaptive-coverage-card__question-text">
                        &ldquo;{meta.question}&rdquo;
                      </p>
                    </div>

                    {/* Operational Reality / Audit Reason */}
                    <div className="adaptive-coverage-card__reason-box">
                      <p className="adaptive-coverage-card__reason">
                        {s.summary_reason}
                      </p>
                    </div>

                    {/* Actionable Unlock Recipe or Live Confirmation */}
                    {isNeedsInputs && s.missing_prerequisites && s.missing_prerequisites.length > 0 && (
                      <div className="adaptive-coverage-card__unlock">
                        <div className="adaptive-coverage-card__unlock-header">
                          <Sparkles size={13} />
                          <span>To Unlock this HR Playbook:</span>
                        </div>
                        <div className="adaptive-coverage-card__chips">
                          {s.missing_prerequisites.map((prereq, idx) => (
                            <span key={idx} className="adaptive-coverage-chip">
                              + {prereq}
                            </span>
                          ))}
                        </div>
                        {onNavigateTab && (
                          <button
                            type="button"
                            onClick={() => onNavigateTab("explorer")}
                            className="adaptive-coverage-unlock-action"
                            title="Open Data Explorer to map source columns"
                          >
                            <span>Map in Data Explorer</span>
                            <ArrowRight size={12} />
                          </button>
                        )}
                      </div>
                    )}

                    {isCompleted && (
                      <div className="adaptive-coverage-card__live-indicator">
                        <CheckCircle2 size={13} />
                        <span>Active in Executive Dashboard · Verified Findings Generated</span>
                      </div>
                    )}
                  </article>
                );
              })
            )}
          </div>
        </div>
      )}
    </section>
  );
}
