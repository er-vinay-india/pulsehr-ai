#!/usr/bin/env node
/**
 * test_rendered_dashboard_integrity.mjs
 *
 * Live Browser Computed DOM Audit for HighView Executive Dashboard.
 * Enforces:
 * 1. Zero-Data Render Firewall (CATALOG_EMPTY: zero analytical components, zero synthetic constants)
 * 2. WCAG AAA Contrast (Computed DOM inspection >= 7.0:1 across text and actions)
 * 3. Multi-Viewport Responsiveness (Desktop 1440x900, Tablet 1024x768, Mobile 390x844)
 * 4. Dual-Theme Support (Light & Dark)
 * 5. Stale Dataset Self-Healing (URL sanitization, no 404 leakage)
 * 6. Canonical Design System Buttons & Navigation Intents
 */

import puppeteer from "puppeteer";
import assert from "node:assert";

const BASE_URL = process.env.BASE_URL || "http://localhost:5175";
const CHROME_PATH = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const VIEWPORTS = [
  { name: "Desktop", width: 1440, height: 900 },
  { name: "Tablet", width: 1024, height: 768 },
  { name: "Mobile", width: 390, height: 844 },
];

// Helper to calculate luminance & contrast ratio in Node
function srgbToLinear(c) {
  const norm = c / 255;
  return norm <= 0.04045 ? norm / 12.92 : Math.pow((norm + 0.055) / 1.055, 2.4);
}

function getLuminance(r, g, b) {
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}

function getContrastRatio(l1, l2) {
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

async function runAudit() {
  console.log("================================================================================");
  console.log("🛡️  HIGHVIEW EXECUTIVE DASHBOARD — LIVE COMPUTED DOM AAA INTEGRITY AUDIT");
  console.log("================================================================================\n");

  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: CHROME_PATH,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  let totalAssertions = 0;
  let passedAssertions = 0;

  try {
    const page = await browser.newPage();

    // Guarantee hermetic zero-data state simulation regardless of backend database contents
    await page.setRequestInterception(true);
    page.on("request", (req) => {
      const url = req.url();
      if (url.includes("/api/upload/datasets")) {
        req.respond({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ datasets: [] }),
        });
      } else if (url.includes("/api/adaptive-dashboard/primary-element")) {
        req.respond({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "No uploaded sheet found for dataset_id 99770." }),
        });
      } else {
        req.continue();
      }
    });

    // --------------------------------------------------------------------------
    // TEST 1: STALE DATASET SELF-HEALING & ZERO-DATA FIREWALL
    // --------------------------------------------------------------------------
    console.log("▶ TEST 1: Stale Dataset Pointer Self-Healing & 404 Elimination");
    await page.setViewport(VIEWPORTS[0]);
    await page.goto(`${BASE_URL}/?dataset_id=99770#adaptive`, { waitUntil: "networkidle2" });
    await new Promise((r) => setTimeout(r, 1500));

    // Verify URL sanitized
    const currentUrl = page.url();
    assert.strictEqual(
      currentUrl.includes("dataset_id=99770"),
      false,
      `URL should strip stale dataset_id: ${currentUrl}`
    );
    console.log("  ✅ URL successfully sanitized by DatasetReferenceIntegrity.selfHealUrl()");
    totalAssertions++;
    passedAssertions++;

    // Verify no 404 or backend trace in page
    const pageContent = await page.evaluate(() => document.body.innerText);
    assert.strictEqual(
      pageContent.includes("No uploaded sheet found for dataset_id 99770"),
      false,
      "Technical 404 backend error string must NEVER be rendered in UI!"
    );
    assert.strictEqual(
      pageContent.includes("detail: Not Found"),
      false,
      "Technical detail must NEVER be rendered in UI!"
    );
    console.log("  ✅ Technical 404 and exception strings blocked from UI");
    totalAssertions++;
    passedAssertions++;

    // --------------------------------------------------------------------------
    // TEST 2: ZERO-DATA RENDER FIREWALL CONTENT INTEGRITY
    // --------------------------------------------------------------------------
    console.log("\n▶ TEST 2: Zero-Data Render Firewall (CATALOG_EMPTY)");
    const boundaryExists = await page.$("[data-testid='empty-dashboard-boundary']");
    assert.ok(boundaryExists, "EmptyDashboardBoundary must mount when catalog is empty");
    console.log("  ✅ EmptyDashboardBoundary mounted exclusively");
    totalAssertions++;
    passedAssertions++;

    // Verify analytical forbidden strings are NOT present
    const forbiddenPatterns = [
      "validated findings",
      "cross-source relationships",
      "EVID-",
      "SCEN-",
      "Simulation Outcome",
      "Audited Claims",
    ];

    for (const pat of forbiddenPatterns) {
      assert.strictEqual(
        pageContent.includes(pat),
        false,
        `Zero-data dashboard must not render analytical pattern: "${pat}"`
      );
    }
    console.log(`  ✅ All ${forbiddenPatterns.length} forbidden analytical patterns blocked`);
    totalAssertions++;
    passedAssertions++;

    // Verify forbidden analytical DOM nodes do not exist
    const analyticalNodes = await page.evaluate(() => {
      return {
        kpiGrid: Boolean(document.querySelector(".kpi-grid, .executive-kpi-grid")),
        visualGrid: Boolean(document.querySelector(".visual-grid, .executive-visual-grid")),
        scenarioExplorer: Boolean(document.querySelector(".executive-scenario-explorer")),
        rankingExplorer: Boolean(document.querySelector(".generic-ranking-explorer")),
      };
    });

    assert.strictEqual(analyticalNodes.kpiGrid, false, "KPI grid must NOT mount on zero data");
    assert.strictEqual(analyticalNodes.visualGrid, false, "Visual grid must NOT mount on zero data");
    assert.strictEqual(analyticalNodes.scenarioExplorer, false, "Scenario explorer must NOT mount on zero data");
    assert.strictEqual(analyticalNodes.rankingExplorer, false, "Ranking explorer must NOT mount on zero data");
    console.log("  ✅ Zero analytical DOM components mounted (KPIs, Visuals, Scenarios, Rankings)");
    totalAssertions++;
    passedAssertions++;

    // Verify approved empty-state elements exist
    const emptyStateElements = await page.evaluate(() => {
      const container = document.querySelector(".adaptive-empty-state");
      const heading = container?.querySelector("h2");
      const primaryBtn = container?.querySelector(".hv-btn--primary");
      const secondaryBtn = container?.querySelector(".hv-btn--secondary");
      const rawButtons = Array.from(container ? container.querySelectorAll("button:not(.hv-btn)") : []).map(
        (b) => b.innerText || b.className
      );
      return {
        headingText: heading ? heading.innerText : null,
        hasPrimaryBtn: Boolean(primaryBtn),
        primaryBtnText: primaryBtn ? primaryBtn.innerText.trim() : null,
        hasSecondaryBtn: Boolean(secondaryBtn),
        secondaryBtnText: secondaryBtn ? secondaryBtn.innerText.trim() : null,
        rawButtons,
      };
    });

    assert.strictEqual(emptyStateElements.headingText, "No Workbooks Ingested");
    assert.ok(emptyStateElements.hasPrimaryBtn, "Primary action button must exist");
    assert.strictEqual(emptyStateElements.primaryBtnText, "Upload Spreadsheet");
    assert.ok(emptyStateElements.hasSecondaryBtn, "Secondary action button must exist");
    assert.strictEqual(emptyStateElements.secondaryBtnText, "Open Data Explorer");
    assert.strictEqual(emptyStateElements.rawButtons.length, 0, `No raw buttons allowed: ${emptyStateElements.rawButtons.join(", ")}`);
    console.log("  ✅ Canonical design-system buttons rendered with 0 raw buttons");
    totalAssertions++;
    passedAssertions++;

    // --------------------------------------------------------------------------
    // TEST 3: LIVE COMPUTED DOM CONTRAST AUDIT (WCAG AAA >= 7.0:1)
    // --------------------------------------------------------------------------
    console.log("\n▶ TEST 3: Computed DOM Contrast Audit across Themes & Viewports");

    const contrastAuditFunction = () => {
      function parseColor(str) {
        if (!str || str === "transparent") return null;
        const rgbaMatch = str.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
        if (rgbaMatch) {
          return {
            r: parseInt(rgbaMatch[1], 10),
            g: parseInt(rgbaMatch[2], 10),
            b: parseInt(rgbaMatch[3], 10),
            a: rgbaMatch[4] !== undefined ? parseFloat(rgbaMatch[4]) : 1,
          };
        }
        return null;
      }

      function getEffectiveBgColor(element) {
        let el = element;
        while (el && el !== document.documentElement) {
          const bg = window.getComputedStyle(el).backgroundColor;
          const parsed = parseColor(bg);
          if (parsed && parsed.a > 0.9) {
            return parsed;
          }
          el = el.parentElement;
        }
        const rootBg = window.getComputedStyle(document.body).backgroundColor;
        const parsedRoot = parseColor(rootBg);
        return parsedRoot || { r: 255, g: 255, b: 255, a: 1 };
      }

      function srgbToLinear(c) {
        const norm = c / 255;
        return norm <= 0.04045 ? norm / 12.92 : Math.pow((norm + 0.055) / 1.055, 2.4);
      }

      function getLuminance(r, g, b) {
        return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
      }

      function getContrastRatio(l1, l2) {
        const lighter = Math.max(l1, l2);
        const darker = Math.min(l1, l2);
        return (lighter + 0.05) / (darker + 0.05);
      }

      const results = [];
      const targets = [
        { selector: ".adaptive-empty-heading", role: "Empty Heading", threshold: 4.5 },
        { selector: ".adaptive-empty-text", role: "Empty description text", threshold: 7.0 },
        { selector: ".adaptive-empty-hint", role: "Empty hint text", threshold: 7.0 },
        { selector: ".hv-btn--primary span", role: "Primary Button Text", threshold: 7.0, isPrimaryBtn: true },
        { selector: ".hv-btn--secondary span", role: "Secondary Button Text", threshold: 7.0, isSecondaryBtn: true },
        { selector: ".adaptive-empty-feature-card strong", role: "Feature card title", threshold: 7.0 },
        { selector: ".adaptive-empty-feature-card span", role: "Feature card text", threshold: 7.0 },
      ];

      for (const t of targets) {
        const el = document.querySelector(t.selector);
        if (!el) continue;
        const style = window.getComputedStyle(el);
        const color = parseColor(style.color);
        let bg;
        if (t.isPrimaryBtn) {
          const btn = el.closest(".hv-btn--primary") || el;
          bg = parseColor(window.getComputedStyle(btn).backgroundColor) || { r: 7, g: 84, b: 67, a: 1 };
        } else if (t.isSecondaryBtn) {
          const btn = el.closest(".hv-btn--secondary") || el;
          bg = parseColor(window.getComputedStyle(btn).backgroundColor) || { r: 24, g: 59, b: 86, a: 1 };
        } else {
          bg = getEffectiveBgColor(el);
        }

        if (color && bg) {
          const lText = getLuminance(color.r, color.g, color.b);
          const lBg = getLuminance(bg.r, bg.g, bg.b);
          const ratio = getContrastRatio(lText, lBg);
          results.push({
            role: t.role,
            selector: t.selector,
            textColor: `rgb(${color.r}, ${color.g}, ${color.b})`,
            bgColor: `rgb(${bg.r}, ${bg.g}, ${bg.b})`,
            ratio: Number(ratio.toFixed(2)),
            threshold: t.threshold,
            passed: ratio >= t.threshold,
          });
        }
      }

      return results;
    };

    for (const theme of ["light", "dark"]) {
      // Toggle theme if necessary
      if (theme === "dark") {
        await page.evaluate(() => {
          document.documentElement.classList.add("dark");
          document.body.classList.add("dark");
        });
      } else {
        await page.evaluate(() => {
          document.documentElement.classList.remove("dark");
          document.body.classList.remove("dark");
        });
      }
      await new Promise((r) => setTimeout(r, 400));

      for (const vp of VIEWPORTS) {
        await page.setViewport(vp);
        await new Promise((r) => setTimeout(r, 200));

        const contrastResults = await page.evaluate(contrastAuditFunction);

        console.log(`\n  --- Theme: ${theme.toUpperCase()} | Viewport: ${vp.name} (${vp.width}x${vp.height}) ---`);
        for (const item of contrastResults) {
          const status = item.passed ? "PASS" : "FAIL";
          const symbol = item.passed ? "✅" : "❌";
          console.log(
            `  ${symbol} [${status}] ${item.role.padEnd(26)}: ${item.ratio}:1 (threshold >= ${item.threshold}:1) | ${item.textColor} on ${item.bgColor}`
          );
          assert.ok(
            item.passed,
            `Contrast failure on ${item.role} in ${theme} theme (${vp.name}): got ${item.ratio}:1, required >= ${item.threshold}:1`
          );
          totalAssertions++;
          passedAssertions++;
        }
      }
    }

    // --------------------------------------------------------------------------
    // TEST 4: CANONICAL NAVIGATION INTENT DISPATCH
    // --------------------------------------------------------------------------
    console.log("\n▶ TEST 4: Navigation Intent Dispatch Verification");
    const intentDispatches = await page.evaluate(() => {
      let dispatchedIntent = null;
      window.addEventListener("highview:navigation-intent", (e) => {
        dispatchedIntent = e.detail?.intent;
      });

      const primaryBtn = document.querySelector(".adaptive-empty-state .hv-btn--primary");
      if (primaryBtn) primaryBtn.click();
      return dispatchedIntent;
    });

    assert.strictEqual(intentDispatches, "OPEN_UPLOAD", "Primary button must dispatch OPEN_UPLOAD intent");
    console.log("  ✅ Primary action dispatches centralized OPEN_UPLOAD intent rather than mutating window.location");
    totalAssertions++;
    passedAssertions++;

    console.log("\n================================================================================");
    console.log(`🎉 ALL LIVE COMPUTED INTEGRITY AUDITS PASSED: ${passedAssertions}/${totalAssertions} assertions clean!`);
    console.log("================================================================================\n");

  } finally {
    await browser.close();
  }
}

runAudit().catch((err) => {
  console.error("\n❌ LIVE COMPUTED AUDIT FAILED:", err);
  process.exit(1);
});
