#!/usr/bin/env node
/**
 * lint_dashboard_anti_bypass.mjs
 *
 * HighView Executive Dashboard Layer Integrity & Anti-Bypass Static Linter.
 * Enforces executable architectural boundaries across the 5 HighView layers:
 * - Layer 1: Governed Truth (no synthetic analytical constants ?? 73, ?? 3)
 * - Layer 2: Design System (no raw <button>, no shadowing .btn-primary)
 * - Layer 3: Theme Tokens (no unauthorized hex/rgb literals outside tokens)
 * - Layer 4: Centralized Routing (no direct window.location / history mutations)
 * - Layer 5: Error Firewall (no raw backend exceptions/404s rendered directly)
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");

/**
 * Auto-discover all dashboard surfaces, components, and styles dynamically.
 * Scans:
 * - frontend/src/pages/AdaptiveDashboardPage.*
 * - frontend/src/components/adaptive/**
 * - frontend/src/styles/adaptive-dashboard.*
 */
export function discoverDashboardFiles(baseDir = rootDir) {
  const discovered = new Set();

  // 1. Pages: src/pages/AdaptiveDashboardPage.*
  const pagesDir = path.join(baseDir, "src/pages");
  if (fs.existsSync(pagesDir)) {
    for (const f of fs.readdirSync(pagesDir)) {
      if (f.startsWith("AdaptiveDashboardPage.")) {
        discovered.add(path.join("src/pages", f));
      }
    }
  }

  // 2. Components: src/components/adaptive/**
  const adaptiveDir = path.join(baseDir, "src/components/adaptive");
  function scanDir(dir, prefix) {
    if (!fs.existsSync(dir)) return;
    for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
      if (item.isDirectory()) {
        scanDir(path.join(dir, item.name), path.join(prefix, item.name));
      } else if (item.isFile() && /\.(jsx?|tsx?|scss|css)$/.test(item.name)) {
        discovered.add(path.join(prefix, item.name));
      }
    }
  }
  scanDir(adaptiveDir, "src/components/adaptive");

  // 3. Registered styles: src/styles/adaptive-dashboard.*
  const stylesDir = path.join(baseDir, "src/styles");
  if (fs.existsSync(stylesDir)) {
    for (const f of fs.readdirSync(stylesDir)) {
      if (f.includes("adaptive-dashboard")) {
        discovered.add(path.join("src/styles", f));
      }
    }
  }

  return Array.from(discovered).sort();
}

export function lintContent(content, filename) {
  const violations = [];
  const lines = content.split("\n");

  for (let idx = 0; idx < lines.length; idx++) {
    const lineNum = idx + 1;
    const line = lines[idx];
    const trimmed = line.trim();

    // Skip comment lines
    if (trimmed.startsWith("//") || trimmed.startsWith("/*") || trimmed.startsWith("*")) {
      continue;
    }

    // 1. RAW INTERACTIVE ELEMENT GUARD
    // Forbids raw <button> in dashboard production components
    if (filename.endsWith(".jsx") || filename.endsWith(".tsx")) {
      if (/<button\b/.test(line)) {
        violations.push({
          rule: "no-raw-interactive-element",
          line: lineNum,
          message: "Raw <button> is forbidden. Use canonical <Button>, <IconButton>, or <ActionIconButton>.",
          snippet: trimmed,
        });
      }
      if (/<a\b[^>]*\bonClick\b[^>]*\b(location|hash|navigate)\b/.test(line)) {
        violations.push({
          rule: "no-raw-interactive-element",
          line: lineNum,
          message: "Raw <a> used as interactive navigation button is forbidden. Use canonical <Button>.",
          snippet: trimmed,
        });
      }
    }

    // 2. DESIGN SYSTEM SHADOWING GUARD (in SCSS)
    if (filename.endsWith(".scss") || filename.endsWith(".css")) {
      if (/^\s*\.(btn-primary|btn-secondary)\b/.test(line)) {
        violations.push({
          rule: "no-design-system-shadowing",
          line: lineNum,
          message: "Page-local definition of canonical button classes (.btn-primary, .btn-secondary) is forbidden.",
          snippet: trimmed,
        });
      }
    }

    // 3. ROUTING ANTI-BYPASS GUARD
    // Forbids direct mutation of window.location or history
    if (
      /window\.location\.(hash|href)\s*=/.test(line) ||
      /\blocation\.href\s*=/.test(line) ||
      /history\.(pushState|replaceState)\(/.test(line)
    ) {
      // Exclude DatasetReferenceIntegrity.js which is the dedicated contract for replaceState
      if (!filename.includes("DatasetReferenceIntegrity.js")) {
        violations.push({
          rule: "no-raw-navigation-mutation",
          line: lineNum,
          message: "Direct window.location or history mutation is forbidden. Use dispatchNavigationIntent.",
          snippet: trimmed,
        });
      }
    }

    // 4. ANALYTICAL FALLBACK CONSTANT GUARD
    // Forbids synthetic numerical fallbacks on analytical variables (e.g. ?? 73, ?? 3, || 100)
    const analyticalFallbackMatch = line.match(
      /(evidence_count|relationship_count|claims|findings|candidate_count|kpi|bench|variance|score|metric|count)\s*(\?\?|\|\|)\s*([1-9]\d*(\.\d+)?)/i
    );
    if (analyticalFallbackMatch) {
      violations.push({
        rule: "no-analytical-fallback-constants",
        line: lineNum,
        message: `Synthetic analytical fallback "${analyticalFallbackMatch[0]}" is forbidden. Missing != fabricated count.`,
        snippet: trimmed,
      });
    }

    // Also flag direct ?? 73 or ?? 3 anywhere in JSX expressions
    const magicNumberMatch = line.match(/(\?\?|\|\|)\s*(73|3)\b/);
    if (magicNumberMatch) {
      violations.push({
        rule: "no-analytical-fallback-constants",
        line: lineNum,
        message: `Hardcoded synthetic fallback constant "${magicNumberMatch[0]}" is strictly forbidden.`,
        snippet: trimmed,
      });
    }

    // 5. DIRECT BACKEND ERROR RENDERING GUARD
    // Forbids directly rendering un-sanitized err.message or response.data.detail
    if (
      /\{\s*(error|err)\.message\s*\}/.test(line) ||
      /\{\s*response\.data\.detail\s*\}/.test(line) ||
      /\{\s*String\((error|err)\)\s*\}/.test(line)
    ) {
      violations.push({
        rule: "no-raw-backend-error-rendering",
        line: lineNum,
        message: "Rendering un-sanitized backend error messages is forbidden. Use sanitizeError() and ProductError.",
        snippet: trimmed,
      });
    }

    // 6. RAW LITERAL COLOR GUARD (outside tokens/themes)
    // In JSX style objects or CSS, disallow raw #hex unless explicit token or canvas config
    const isCanvasOrChartConfig = filename.includes("VisualSpecRenderer") || filename.includes("ChartConfig") || filename.includes("tokens");
    if (!isCanvasOrChartConfig && (filename.endsWith(".jsx") || filename.endsWith(".scss") || filename.endsWith(".tsx"))) {
      // Match #hex color patterns
      const hexMatches = line.match(/#[0-9a-fA-F]{3,8}\b/g);
      if (hexMatches) {
        for (const hex of hexMatches) {
          // Allow comments and known acceptable design-system tokens fallbacks (e.g. var(--action-primary-bg, #075443))
          const isTokenFallback = line.includes(`var(`) && line.includes(hex);
          if (!isTokenFallback) {
            violations.push({
              rule: "no-raw-literal-colors",
              line: lineNum,
              message: `Literal color "${hex}" is forbidden. Must use semantic theme tokens or CSS variables.`,
              snippet: trimmed,
            });
          }
        }
      }
    }
  }

  return violations;
}

export function runDashboardAntiBypassLint() {
  console.log("🛡️  Starting HighView Executive Dashboard Layer Integrity & Anti-Bypass Audit...\n");

  let totalViolations = 0;
  const filesToScan = discoverDashboardFiles(rootDir);
  console.log(`🔍 Auto-discovered ${filesToScan.length} dashboard surface files to audit:\n`);
  for (const f of filesToScan) {
    console.log(`   - ${f}`);
  }
  console.log("");

  for (const relPath of filesToScan) {
    const fullPath = path.join(rootDir, relPath);
    if (!fs.existsSync(fullPath)) {
      console.warn(`⚠️  File not found: ${relPath}`);
      continue;
    }

    const content = fs.readFileSync(fullPath, "utf-8");
    const fileViolations = lintContent(content, relPath);

    if (fileViolations.length > 0) {
      console.error(`❌ VIOLATIONS IN: ${relPath}`);
      for (const v of fileViolations) {
        console.error(`   [Line ${v.line}] [${v.rule}]: ${v.message}`);
        console.error(`     Snippet: ${v.snippet}`);
      }
      console.error("");
      totalViolations += fileViolations.length;
    } else {
      console.log(`✅ PASS: ${relPath} (0 layer bypasses)`);
    }
  }

  console.log("\n--------------------------------------------------");
  if (totalViolations === 0) {
    console.log("🎉 ALL DASHBOARD FILES COMPLY WITH ARCHITECTURAL LAYER CONTRACTS!\n");
    return true;
  } else {
    console.error(`❌ AUDIT FAILED: ${totalViolations} architectural layer bypasses detected.\n`);
    return false;
  }
}

// Direct execution
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const success = runDashboardAntiBypassLint();
  process.exit(success ? 0 : 1);
}
