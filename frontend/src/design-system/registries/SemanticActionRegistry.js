/**
 * SemanticActionRegistry.js
 *
 * Single authoritative registry of executive action icons, tooltips, and accessible labels.
 * Individual cards and toolbars must NEVER invent local button styles, arbitrary icons,
 * or inconsistent action text.
 */
import {
  Search,
  Eye,
  ArrowUpRight,
  ShieldCheck,
  Trophy,
  ListOrdered,
  Network,
  BarChart2,
  TrendingUp,
  Grid3x3,
  Sliders,
  Presentation,
  RefreshCw,
  Volume2,
  MoreHorizontal,
  X,
  Maximize2,
  ChevronRight,
  HelpCircle,
  FileSpreadsheet
} from "lucide-react";

export const ACTION_DEFINITIONS = {
  inspect: {
    icon: Search,
    secondaryIcon: Eye,
    label: "Inspect",
    tooltip: "Quick Inspect details and underlying grain",
    ariaPattern: (title) => `Inspect ${title || "finding"}`
  },
  deep_dive: {
    icon: ArrowUpRight,
    label: "Deep Dive",
    tooltip: "Open in Data Explorer",
    ariaPattern: (title) => `Open ${title || "finding"} in Data Explorer`
  },
  explorer: {
    icon: ArrowUpRight,
    label: "Data Explorer",
    tooltip: "Explore granular breakdown in Data Explorer",
    ariaPattern: (title) => `Open ${title || "dataset"} in Data Explorer`
  },
  evidence: {
    icon: ShieldCheck,
    label: "Evidence",
    tooltip: "View mathematical evidence lineage and audit record",
    ariaPattern: (title) => `View evidence for ${title || "finding"}`
  },
  ranking: {
    icon: Trophy,
    secondaryIcon: ListOrdered,
    label: "Ranking",
    tooltip: "View full comparative ranking across population",
    ariaPattern: (title) => `View rankings for ${title || "metric"}`
  },
  relationship: {
    icon: Network,
    label: "Relationship",
    tooltip: "Analyze cross-dimensional relationships and correlations",
    ariaPattern: (title) => `View relationships for ${title || "metric"}`
  },
  distribution: {
    icon: BarChart2,
    label: "Distribution",
    tooltip: "Analyze population distribution and dispersion",
    ariaPattern: (title) => `View distribution for ${title || "metric"}`
  },
  trend: {
    icon: TrendingUp,
    label: "Trend",
    tooltip: "Examine temporal cadence and trajectory",
    ariaPattern: (title) => `View trend for ${title || "metric"}`
  },
  matrix: {
    icon: Grid3x3,
    label: "Matrix",
    tooltip: "Explore two-dimensional cross-tabulation matrix",
    ariaPattern: (title) => `View matrix for ${title || "data"}`
  },
  scenario: {
    icon: Sliders,
    label: "Scenario Simulator",
    tooltip: "Simulate forward policy adjustments and capacity impact",
    ariaPattern: (title) => `Open scenario simulator for ${title || "dashboard"}`
  },
  presentation: {
    icon: Presentation,
    label: "Create Presentation",
    tooltip: "Generate board-ready executive slide deck from ground truth",
    ariaPattern: () => "Create executive presentation deck"
  },
  refresh: {
    icon: RefreshCw,
    label: "Refresh",
    tooltip: "Re-evaluate real-time metrics and evidence graph",
    ariaPattern: () => "Refresh live dashboard data"
  },
  listen: {
    icon: Volume2,
    label: "Listen",
    tooltip: "Audio executive briefing with synthesized narration",
    ariaPattern: () => "Listen to synthesized executive audio briefing"
  },
  more: {
    icon: MoreHorizontal,
    label: "More Options",
    tooltip: "View secondary diagnostic actions",
    ariaPattern: () => "More options"
  },
  close: {
    icon: X,
    label: "Close",
    tooltip: "Dismiss inspection panel (ESC)",
    ariaPattern: () => "Close panel"
  },
  expand: {
    icon: Maximize2,
    label: "Expand",
    tooltip: "Expand visual view",
    ariaPattern: (title) => `Expand ${title || "visual"}`
  }
};

/**
 * Resolves semantic action details.
 * @param {string} actionKey - Key from ACTION_DEFINITIONS (e.g. "inspect", "deep_dive")
 * @param {string} [contextTitle] - Optional title for accessible aria-label formatting
 * @returns {object} Action metadata including icon component, label, tooltip, and ariaLabel
 */
export function getSemanticAction(actionKey, contextTitle = "") {
  const normKey = (actionKey || "").toLowerCase();
  const def = ACTION_DEFINITIONS[normKey] || ACTION_DEFINITIONS.inspect;

  return {
    key: normKey,
    Icon: def.icon,
    label: def.label,
    tooltip: def.tooltip,
    ariaLabel: def.ariaPattern(contextTitle)
  };
}

export default getSemanticAction;
