#!/usr/bin/env node
/**
 * test_anti_bypass_linter_negative.mjs
 *
 * Negative verification suite for lint_dashboard_anti_bypass.mjs.
 * Verifies that the linter correctly detects and rejects:
 * 1. Raw <button> elements
 * 2. Page-local .btn-primary / .btn-secondary CSS definitions
 * 3. Literal #hex color codes outside tokens
 * 4. Direct window.location / history mutations
 * 5. Synthetic analytical constants (?? 73, ?? 3, || 10, count || 2)
 * 6. Direct un-sanitized backend error rendering ({error.message})
 */

import assert from "node:assert";
import { lintContent } from "./lint_dashboard_anti_bypass.mjs";

console.log("🧪 Running Anti-Bypass Linter Negative Verification Suite...\n");

const tests = [
  {
    name: "Detects raw <button> in JSX",
    filename: "src/components/adaptive/FakeComponent.jsx",
    content: `
      export default function BadComponent() {
        return <button onClick={() => {}}>Click Me</button>;
      }
    `,
    expectedRule: "no-raw-interactive-element",
  },
  {
    name: "Detects page-local .btn-primary in SCSS",
    filename: "src/styles/bad-styles.scss",
    content: `
      .bad-container {
        .btn-primary {
          background-color: blue;
        }
      }
    `,
    expectedRule: "no-design-system-shadowing",
  },
  {
    name: "Detects literal hex colors outside design tokens",
    filename: "src/components/adaptive/BadColorComponent.jsx",
    content: `
      export default function BadColor() {
        return <div style={{ color: "#2563eb" }}>Text</div>;
      }
    `,
    expectedRule: "no-raw-literal-colors",
  },
  {
    name: "Detects direct window.location.hash mutation",
    filename: "src/components/adaptive/BadRoutingComponent.jsx",
    content: `
      function navigate() {
        window.location.hash = "upload";
      }
    `,
    expectedRule: "no-raw-navigation-mutation",
  },
  {
    name: "Detects direct window.location.href mutation",
    filename: "src/components/adaptive/BadRoutingComponent.jsx",
    content: `
      function navigate() {
        window.location.href = "/?tab=explorer";
      }
    `,
    expectedRule: "no-raw-navigation-mutation",
  },
  {
    name: "Detects synthetic analytical fallback constant '?? 73'",
    filename: "src/components/adaptive/BadTruthComponent.jsx",
    content: `
      function renderMetric(val) {
        return <span>{val ?? 73}</span>;
      }
    `,
    expectedRule: "no-analytical-fallback-constants",
  },
  {
    name: "Detects synthetic analytical fallback constant '?? 3'",
    filename: "src/components/adaptive/BadTruthComponent.jsx",
    content: `
      function renderCount(val) {
        const total = val ?? 3;
        return total;
      }
    `,
    expectedRule: "no-analytical-fallback-constants",
  },
  {
    name: "Detects count || 2 synthetic fallback",
    filename: "src/components/adaptive/BadTruthComponent.jsx",
    content: `
      function renderSheets(data) {
        return <div>{data.sheet_count || 2} sheets</div>;
      }
    `,
    expectedRule: "no-analytical-fallback-constants",
  },
  {
    name: "Detects un-sanitized error.message rendering",
    filename: "src/components/adaptive/BadErrorComponent.jsx",
    content: `
      function ErrorView({ error }) {
        return <div>{error.message}</div>;
      }
    `,
    expectedRule: "no-raw-backend-error-rendering",
  },
];

let passedCount = 0;

for (const test of tests) {
  const violations = lintContent(test.content, test.filename);
  const matched = violations.find((v) => v.rule === test.expectedRule);
  if (matched) {
    console.log(`✅ PASS: ${test.name}`);
    passedCount++;
  } else {
    console.error(`❌ FAIL: ${test.name}`);
    console.error(`   Expected rule "${test.expectedRule}" but received:`, violations);
    process.exit(1);
  }
}

// ---------------------------------------------------------------------------
// SECTION 13: AUTO-DISCOVERY OF FUTURE DASHBOARD SURFACE INTEGRATION TEST
// ---------------------------------------------------------------------------
console.log("\n🧪 Running Section 13: FutureDashboardSurface Auto-Discovery Test...");

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { discoverDashboardFiles } from "./lint_dashboard_anti_bypass.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");
const futureFilePath = path.join(rootDir, "src/components/adaptive/FutureDashboardSurface.jsx");

const FUTURE_SURFACE_BAD_CONTENT = `
import React from "react";

export default function FutureDashboardSurface({ error, stats }) {
  const handleClick = () => {
    window.location.hash = "unauthorized_tab";
  };

  const count = stats?.finding_count ?? 73;

  return (
    <div style={{ backgroundColor: "#2563EB", color: "#ffffff" }}>
      <h2>Future Dashboard Surface ({count})</h2>
      {error && <div>{error.message}</div>}
      <button onClick={handleClick}>Bypass Action</button>
    </div>
  );
}
`;

try {
  // 1. Write deliberate violation file
  fs.writeFileSync(futureFilePath, FUTURE_SURFACE_BAD_CONTENT, "utf-8");

  // 2. Verify auto-discovery found it without config changes
  const discovered = discoverDashboardFiles(rootDir);
  const foundInDiscovered = discovered.some((f) => f.includes("FutureDashboardSurface.jsx"));
  assert(foundInDiscovered, "FutureDashboardSurface.jsx was NOT auto-discovered by linter!");
  console.log("✅ PASS: FutureDashboardSurface.jsx was automatically discovered by anti-bypass linter");

  // 3. Lint the discovered file and verify all 5 deliberate violations are caught
  const content = fs.readFileSync(futureFilePath, "utf-8");
  const violations = lintContent(content, "FutureDashboardSurface.jsx");
  const caughtRules = new Set(violations.map((v) => v.rule));

  assert(caughtRules.has("no-raw-interactive-element"), "Failed to catch <button>");
  assert(caughtRules.has("no-raw-literal-colors"), "Failed to catch #2563EB");
  assert(caughtRules.has("no-raw-navigation-mutation"), "Failed to catch window.location.hash");
  assert(caughtRules.has("no-analytical-fallback-constants"), "Failed to catch ?? 73");
  assert(caughtRules.has("no-raw-backend-error-rendering"), "Failed to catch error.message");

  console.log(`✅ PASS: All 5 deliberate violations caught (${violations.length} total violation flags):`);
  for (const v of violations) {
    console.log(`   - [Line ${v.line}] [${v.rule}]: ${v.message}`);
  }
} finally {
  // Clean up fixture
  if (fs.existsSync(futureFilePath)) {
    fs.unlinkSync(futureFilePath);
  }
}

// Re-verify that after cleanup, FutureDashboardSurface is gone from discovered files
const postCleanupDiscovered = discoverDashboardFiles(rootDir);
assert(!postCleanupDiscovered.some((f) => f.includes("FutureDashboardSurface.jsx")), "Fixture cleanup failed");
console.log("✅ PASS: Temporary fixture cleaned up, repository returns to clean state");

console.log(`\n🎉 Negative Test Suite Passed: ${passedCount + 1}/${tests.length + 1} test suites verified clean.`);

