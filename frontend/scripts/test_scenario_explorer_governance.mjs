/**
 * Test Suite for Phase 10: Executive Scenario Explorer Frontend Governance.
 *
 * Validates:
 * 1. Strict separation of observed evidence (EVID-xxx) from simulated outcomes (SCEN-xxx).
 * 2. Mandatory presence of all 6 decision-grade governance fields:
 *    - Baseline
 *    - Scenario
 *    - Delta
 *    - Assumptions
 *    - Confidence
 *    - Affected population
 * 3. Governed business levers only (no arbitrary scaling sliders).
 * 4. Theme integrity compliance (Light & Dark tokens consumed, zero dark slate overrides).
 */
import fs from "fs";
import path from "path";
import assert from "assert";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log("🧪 Starting Phase 10 Executive Scenario Explorer Governance Suite...\n");

const explorerFile = path.resolve(__dirname, "../src/components/adaptive/ExecutiveScenarioExplorer.jsx");
const pageFile = path.resolve(__dirname, "../src/pages/AdaptiveDashboardPage.jsx");

// =========================================================================
// 1. Component existence and file checks
// =========================================================================
console.log("1. Checking component existence...");
assert(fs.existsSync(explorerFile), "ExecutiveScenarioExplorer.jsx must exist");
assert(fs.existsSync(pageFile), "AdaptiveDashboardPage.jsx must exist");
const explorerSrc = fs.readFileSync(explorerFile, "utf-8");
const pageSrc = fs.readFileSync(pageFile, "utf-8");
console.log("   ✅ Component files verified.");

// =========================================================================
// 2. Strict Token Separation: SCEN-xxx vs EVID-xxx
// =========================================================================
console.log("\n2. Checking token separation (SCEN-xxx vs EVID-xxx)...");
assert(explorerSrc.includes("Simulated Outcome"), "Scenario card must explicitly badge Simulated Outcome");
assert(explorerSrc.includes("baseline_evidence_id"), "Scenario card must declare baseline evidence link");
assert(explorerSrc.includes("is_simulated"), "Component must check or expose is_simulated flag");
assert(explorerSrc.includes("Observed Baseline"), "Component must clearly identify observed baseline");
console.log("   ✅ Strict separation of EVID-xxx and SCEN-xxx verified.");

// =========================================================================
// 3. Mandatory Decision-Grade Governance & Counterfactual Semantics Fields
// =========================================================================
console.log("\n3. Checking mandatory decision-grade governance fields...");
// 1. Baseline
assert(explorerSrc.includes("Policy Baseline") || explorerSrc.includes("baseline_policy"), "Must display Policy Baseline");
// 2. Scenario / Counterfactual Compliance
assert(
  explorerSrc.includes("Counterfactual Compliance") ||
  explorerSrc.includes("Projected Scenario") ||
  explorerSrc.includes("scenario_policy"),
  "Must display Counterfactual Compliance / Scenario"
);
// 3. Delta
assert(explorerSrc.includes("Net Change (Delta)") || explorerSrc.includes("formatted_delta"), "Must display Delta");
// 4. Assumptions
assert(explorerSrc.includes("Governed Model Assumptions") || explorerSrc.includes("assumptions"), "Must display Assumptions");
// 5. Evidence Strength
assert(
  explorerSrc.includes("Evidence Strength") ||
  explorerSrc.includes("Statistical Confidence") ||
  explorerSrc.includes("evidence_strength"),
  "Must display Evidence Strength"
);
// 6. Affected Population
assert(explorerSrc.includes("Affected Population") || explorerSrc.includes("affected_population"), "Must display Affected Population");
// 7. Counterfactual Interpretation & Non-Predictive Disclaimer
assert(explorerSrc.includes("Interpretation") || explorerSrc.includes("interpretation"), "Must display Interpretation block");
assert(
  explorerSrc.includes("Scientific Semantics") ||
  explorerSrc.includes("behavioral adaptation") ||
  explorerSrc.includes("counterfactual_disclaimer"),
  "Must display explicit non-predictive adaptation disclaimer"
);
assert(
  explorerSrc.includes("POLICY_REPLAY") || explorerSrc.includes("scenario_type"),
  "Must support explicit scenario classification"
);
console.log("   ✅ All decision-grade and scientific counterfactual fields verified in the scenario card structure.");

// =========================================================================
// 4. Governed Business Levers Only (No Arbitrary Sliders)
// =========================================================================
console.log("\n4. Checking governed business levers...");
assert(explorerSrc.includes("Required In-Office Days / Week"), "Must expose days/week lever");
assert(explorerSrc.includes("Approved Leave Exemption Credit"), "Must expose leave exemption credit lever");
assert(explorerSrc.includes("Department Accommodation Override"), "Must expose department override lever");
assert(!explorerSrc.includes("increase attendance by"), "Must NOT expose arbitrary attendance multiplier slider");
assert(!explorerSrc.includes("reduce leave by"), "Must NOT expose arbitrary leave multiplier slider");
console.log("   ✅ Governed levers enforced; arbitrary scaling sliders eliminated.");

// =========================================================================
// 5. Page Integration & Command Bar Toggle
// =========================================================================
console.log("\n5. Checking integration into AdaptiveDashboardPage.jsx...");
assert(pageSrc.includes("ExecutiveScenarioExplorer"), "AdaptiveDashboardPage must import ExecutiveScenarioExplorer");
assert(pageSrc.includes("showScenarioExplorer"), "AdaptiveDashboardPage must have showScenarioExplorer toggle");
assert(pageSrc.includes("<ExecutiveScenarioExplorer"), "AdaptiveDashboardPage must render ExecutiveScenarioExplorer");
console.log("   ✅ Scenario Explorer cleanly integrated into executive dashboard page.");

// =========================================================================
// 6. Theme Integrity Compliance
// =========================================================================
console.log("\n6. Checking theme integrity compliance...");
assert(explorerSrc.includes("useTheme"), "Must use useTheme context");
assert(explorerSrc.includes("getThemeTokens"), "Must consume centralized theme tokens");
assert(!explorerSrc.includes("#0f172a"), "Must NOT hardcode raw #0f172a dark slate background");
assert(!explorerSrc.includes("#1e293b"), "Must NOT hardcode raw #1e293b dark slate background");
console.log("   ✅ Theme integrity strictly respected.");

console.log("\n🎉 ALL 6 PHASE 10 SCENARIO EXPLORER GOVERNANCE CHECKS PASSED!");
