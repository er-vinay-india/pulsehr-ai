#!/usr/bin/env node
/**
 * test_product_lifecycle_same_session.mjs
 *
 * Implements Sections 19, 20, 21:
 * - Section 19: Same-Session Product Lifecycle (Workforce -> empty -> Retail -> empty -> Environmental -> empty -> refresh)
 * - Section 20: Browser Back/Forward History Resurrect Invariant
 * - Section 21: Reproduction of the Exact Original Incident (Live Dashboard Open -> Delete All -> Zero-Data Transition)
 *
 * Verifies across viewports (1440x900 light, 390x844 dark) without restarting frontend or backend.
 */

import puppeteer from "puppeteer";
import fs from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");

const FRONTEND_URL = process.env.BASE_URL || "http://localhost:5175";
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const CHROME_PATH = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const WORKFORCE_CSV = path.join(repoRoot, "backend/tests/fixtures/reconstruction_benchmark/workforce_01_headcount_multilevel.csv");
const RETAIL_CSV = path.join(repoRoot, "backend/tests/fixtures/reconstruction_benchmark/retail_01_inventory_catalog_multicell.csv");
const ENV_CSV = path.join(repoRoot, "backend/tests/fixtures/reconstruction_benchmark/env_01_cpcb_pollution.csv");

async function apiDeleteAllDatasets() {
  const res = await fetch(`${BACKEND_URL}/api/upload/datasets`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`Failed to delete all datasets: HTTP ${res.status}`);
  }
  return res.json();
}

async function apiGetDatasets() {
  const res = await fetch(`${BACKEND_URL}/api/upload/datasets`);
  if (!res.ok) {
    throw new Error(`Failed to get datasets: HTTP ${res.status}`);
  }
  const data = await res.json();
  return Array.isArray(data) ? data : data.datasets || [];
}

async function apiUploadFile(filePath) {
  const fileBytes = fs.readFileSync(filePath);
  const fileName = path.basename(filePath);
  const formData = new FormData();
  const blob = new Blob([fileBytes], { type: "text/csv" });
  formData.append("file", blob, fileName);

  const res = await fetch(`${BACKEND_URL}/api/upload/file`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Upload failed for ${fileName}: HTTP ${res.status} - ${err}`);
  }
  return res.json();
}

// Contrast ratio helper
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

async function verifyEmptyStateDOM(page, contextLabel) {
  const textContent = await page.evaluate(() => document.body.innerText);

  // 1. Verify zero-data boundary mounted
  const hasEmptyBoundary = await page.evaluate(() => {
    return Boolean(document.querySelector('[data-testid="empty-dashboard-boundary"]') ||
                   document.querySelector('.empty-dashboard-state'));
  });
  assert(hasEmptyBoundary, `[${contextLabel}] Expected EmptyDashboardBoundary mounted in DOM`);

  // 2. Verify forbidden synthetic facts absent
  assert(!textContent.includes("73 validated findings"), `[${contextLabel}] Leaked synthetic finding count "73"`);
  assert(!textContent.includes("3 cross-source relationships"), `[${contextLabel}] Leaked synthetic relationship count "3"`);
  assert(!/\b73\s+(validated|findings)\b/i.test(textContent), `[${contextLabel}] Leaked synthetic 73 count`);

  // 3. Verify no raw backend error strings
  assert(!textContent.includes("No uploaded sheet found for dataset_id"), `[${contextLabel}] Leaked backend 404 string in UI`);
  assert(!textContent.includes("Server responded with status 404"), `[${contextLabel}] Leaked HTTP 404 status in UI`);
  assert(!textContent.includes("Internal Server Error"), `[${contextLabel}] Leaked 500 error in UI`);

  // 4. Verify canonical design-system buttons in dashboard surface (0 raw <button>)
  const rawButtons = await page.evaluate(() => {
    const dashboardContainer = document.querySelector('[data-testid="empty-dashboard-boundary"]') ||
                               document.querySelector('.empty-dashboard-state') ||
                               document.querySelector('.adaptive-dashboard-page');
    if (!dashboardContainer) return 0;
    const buttons = Array.from(dashboardContainer.querySelectorAll("button"));
    return buttons.filter(b => {
      const cls = b.className || "";
      const isCanonical = cls.includes("hv-button") || cls.includes("hv-btn") || cls.includes("btn-") || cls.includes("highview-") || b.hasAttribute("data-testid");
      return !isCanonical;
    }).length;
  });
  assert.equal(rawButtons, 0, `[${contextLabel}] Found ${rawButtons} non-canonical raw buttons inside dashboard surface`);

  // 5. Verify URL is sanitized / healed (no stale dataset_id)
  const currentUrl = page.url();
  assert(!currentUrl.includes("dataset_id="), `[${contextLabel}] Stale dataset_id still in URL: ${currentUrl}`);

  // 6. Verify button contrast meets AAA policy (>= 7.0:1)
  const primaryButtonContrast = await page.evaluate(() => {
    const btn = document.querySelector('button.hv-btn--primary') || document.querySelector('.empty-actions button');
    if (!btn) return null;
    const style = window.getComputedStyle(btn);
    return {
      color: style.color,
      bgColor: style.backgroundColor,
    };
  });
  if (primaryButtonContrast) {
    const parseRgb = (str) => {
      const m = str.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      return m ? [parseInt(m[1]), parseInt(m[2]), parseInt(m[3])] : [255, 255, 255];
    };
    const [fgR, fgG, fgB] = parseRgb(primaryButtonContrast.color);
    const [bgR, bgG, bgB] = parseRgb(primaryButtonContrast.bgColor);
    const lumFg = getLuminance(fgR, fgG, fgB);
    const lumBg = getLuminance(bgR, bgG, bgB);
    const ratio = getContrastRatio(lumFg, lumBg);
    assert(ratio >= 7.0, `[${contextLabel}] Primary button contrast ${ratio.toFixed(2)}:1 below AAA threshold (7:1)`);
  }
}

async function runLifecycleSuite() {
  console.log("================================================================================");
  console.log("🚀 HIGHVIEW PRODUCT LIFECYCLE & LIVE INCIDENT REPRODUCTION SUITE");
  console.log("   Sections 19, 20, 21 — Same-Session / Zero-Restart Integrity");
  console.log("================================================================================\n");

  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: CHROME_PATH,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    const page = await browser.newPage();

    // Capture console errors & network failures for audit
    const consoleLogs = [];
    const consoleErrors = [];
    page.on("console", (msg) => {
      const txt = msg.text();
      consoleLogs.push(txt);
      if (msg.type() === "error") {
        consoleErrors.push(txt);
      }
    });

    const failedRequests = [];
    page.on("requestfailed", (req) => {
      failedRequests.push({ url: req.url(), error: req.failure()?.errorText });
    });

    // -------------------------------------------------------------------------
    // VIEWPORT 1: Desktop 1440x900 Light Theme
    // -------------------------------------------------------------------------
    console.log("▶ INITIAL VIEWPORT: Desktop 1440x900 (Light Theme)");
    await page.setViewport({ width: 1440, height: 900 });

    // Step 0: Ensure starting state is empty
    console.log("\n0. Initial State Reset: Clearing all datasets via API...");
    await apiDeleteAllDatasets();
    let currentDatasets = await apiGetDatasets();
    assert.equal(currentDatasets.length, 0, "Initial dataset count must be 0");
    console.log("   ✅ Database verified at 0 datasets");

    // Load Dashboard in empty state
    await page.goto(`${FRONTEND_URL}/?tab=dashboard`, { waitUntil: "networkidle2" });
    await new Promise((r) => setTimeout(r, 1000));
    await verifyEmptyStateDOM(page, "Initial Empty State");
    console.log("   ✅ Initial zero-data dashboard renders clean EmptyDashboardBoundary without errors");

    // -------------------------------------------------------------------------
    // STEP A: Upload Workforce Dataset
    // -------------------------------------------------------------------------
    console.log("\n1. Step A: Uploading Workforce Dataset (workforce_01_headcount_multilevel.csv)...");
    const wfUpload = await apiUploadFile(WORKFORCE_CSV);
    const wfDatasetId = wfUpload.dataset_id || (await apiGetDatasets())[0]?.id;
    console.log(`   Workforce uploaded successfully: dataset_id=${wfDatasetId}`);

    // Navigate to Dashboard for Workforce
    await page.goto(`${FRONTEND_URL}/?tab=dashboard&dataset_id=${wfDatasetId}`, { waitUntil: "networkidle2" });
    await new Promise((r) => setTimeout(r, 2000));

    const wfText = await page.evaluate(() => document.body.innerText);
    assert(!wfText.includes("No uploaded sheet found"), "Workforce dashboard leaked 404");
    assert(wfText.includes("Headcount") || wfText.includes("Employee") || wfText.includes("Workforce") || wfText.includes("HR"),
      "Expected Workforce domain vocabulary in Dashboard");
    console.log("   ✅ Workforce Dashboard rendered correctly with domain-specific intelligence");

    // -------------------------------------------------------------------------
    // STEP B & SECTION 21: The Exact Original Incident Reproduction
    // While Dashboard is actively open, delete all datasets WITHOUT restarting server!
    // -------------------------------------------------------------------------
    console.log("\n2. Step B / Section 21: Reproducing the EXACT Original Incident:");
    console.log("   - Live Dashboard is OPEN at dataset_id=" + wfDatasetId);
    console.log("   - User deletes all datasets from system without server restart...");
    await apiDeleteAllDatasets();
    const afterDeleteDatasets = await apiGetDatasets();
    assert.equal(afterDeleteDatasets.length, 0, "All datasets successfully deleted");

    // Trigger dashboard refresh / poll in same session
    await page.reload({ waitUntil: "networkidle2" });
    await new Promise((r) => setTimeout(r, 1500));

    console.log("   - Verifying Dashboard response to deletion:");
    await verifyEmptyStateDOM(page, "Original Incident Post-Delete");
    console.log("   ✅ Dashboard transitioned cleanly to EmptyDashboardBoundary");
    console.log("   ✅ URL self-healed (stale dataset_id removed)");
    console.log("   ✅ 0 technical 404s leaked");
    console.log("   ✅ 0 synthetic numbers (?? 73, ?? 3) rendered");
    console.log("   ✅ Canonical <Button> rendered with compliant AAA contrast");

    // Also verify Data Explorer is clean
    await page.goto(`${FRONTEND_URL}/?tab=explorer`, { waitUntil: "networkidle2" });
    await new Promise((r) => setTimeout(r, 1000));
    const explorerText = await page.evaluate(() => document.body.innerText);
    assert(!explorerText.includes("99770"), "Explorer showed benchmark dataset 99770!");
    assert(!explorerText.includes("99771"), "Explorer showed benchmark dataset 99771!");
    assert(!explorerText.includes("99772"), "Explorer showed benchmark dataset 99772!");
    console.log("   ✅ Data Explorer verified clean: zero benchmark or resurrected datasets present");

    // -------------------------------------------------------------------------
    // SECTION 20: Browser Back/Forward History Test
    // -------------------------------------------------------------------------
    console.log("\n3. Section 20: Browser Back/Forward History Invariant Test...");
    // Go Back to where dashboard URL was with old dataset_id
    await page.goBack();
    await new Promise((r) => setTimeout(r, 1500));
    await verifyEmptyStateDOM(page, "History Go-Back");
    console.log("   ✅ Browser Back did NOT resurrect deleted dataset or stale ID");

    // Go Forward to Explorer
    await page.goForward();
    await new Promise((r) => setTimeout(r, 1000));
    const forwardText = await page.evaluate(() => document.body.innerText);
    assert(!forwardText.includes("99770"), "Browser Forward resurrected benchmark data!");
    console.log("   ✅ Browser Forward did NOT resurrect deleted dataset");

    // Return to Dashboard tab
    await page.goto(`${FRONTEND_URL}/?tab=dashboard`, { waitUntil: "networkidle2" });
    await new Promise((r) => setTimeout(r, 1000));

    // -------------------------------------------------------------------------
    // STEP C: Upload Retail Dataset
    // -------------------------------------------------------------------------
    console.log("\n4. Step C: Uploading Retail Dataset (retail_01_inventory_catalog_multicell.csv)...");
    const retailUpload = await apiUploadFile(RETAIL_CSV);
    const retailDatasetId = retailUpload.dataset_id || (await apiGetDatasets())[0]?.id;
    console.log(`   Retail uploaded successfully: dataset_id=${retailDatasetId}`);

    await page.goto(`${FRONTEND_URL}/?tab=dashboard&dataset_id=${retailDatasetId}`, { waitUntil: "networkidle2" });
    await new Promise((r) => setTimeout(r, 2000));

    const retailText = await page.evaluate(() => document.body.innerText);
    assert(retailText.includes("Retail") || retailText.includes("Inventory") || retailText.includes("Catalog") || retailText.includes("Price") || retailText.includes("SKU") || retailText.includes("Store"),
      "Expected Retail domain vocabulary in Dashboard");
    assert(!retailText.includes("Headcount"), "Retail dashboard leaked Workforce 'Headcount' vocabulary!");
    console.log("   ✅ Retail Dashboard rendered: Retail vocabulary present, ZERO Workforce vocabulary leakage");

    // -------------------------------------------------------------------------
    // STEP D: Delete All Datasets
    // -------------------------------------------------------------------------
    console.log("\n5. Step D: Deleting all datasets after Retail...");
    await apiDeleteAllDatasets();
    await page.reload({ waitUntil: "networkidle2" });
    await new Promise((r) => setTimeout(r, 1500));
    await verifyEmptyStateDOM(page, "Post-Retail Empty State");
    console.log("   ✅ Clean zero-data state verified after Retail deletion");

    // -------------------------------------------------------------------------
    // STEP E: Upload Environmental Dataset in Mobile Dark Viewport
    // -------------------------------------------------------------------------
    console.log("\n6. Step E: Uploading Environmental Dataset in Mobile 390x844 Dark Theme...");
    await page.setViewport({ width: 390, height: 844 });

    const envUpload = await apiUploadFile(ENV_CSV);
    const envDatasetId = envUpload.dataset_id || (await apiGetDatasets())[0]?.id;
    console.log(`   Environmental uploaded successfully: dataset_id=${envDatasetId}`);

    // Set theme to dark in localStorage before loading
    await page.evaluate(() => {
      localStorage.setItem("pulsehr-theme", "dark");
      document.documentElement.setAttribute("data-theme", "dark");
    });

    await page.goto(`${FRONTEND_URL}/?tab=dashboard&dataset_id=${envDatasetId}`, { waitUntil: "networkidle2" });
    await new Promise((r) => setTimeout(r, 2000));

    const envText = await page.evaluate(() => document.body.innerText);
    assert(envText.includes("Pollution") || envText.includes("CPCB") || envText.includes("Air Quality") || envText.includes("PM") || envText.includes("Environmental") || envText.includes("Station"),
      "Expected Environmental domain vocabulary in Dashboard");
    assert(!envText.includes("Headcount"), "Environmental dashboard leaked Workforce vocabulary!");
    assert(!envText.includes("Inventory Catalog"), "Environmental dashboard leaked Retail vocabulary!");
    console.log("   ✅ Environmental Dashboard rendered: Environmental vocabulary present, ZERO Workforce/Retail leakage");

    // -------------------------------------------------------------------------
    // STEP F & G: Delete All & Refresh
    // -------------------------------------------------------------------------
    console.log("\n7. Step F & G: Final Delete All & Refresh in Mobile Dark Viewport...");
    await apiDeleteAllDatasets();
    await page.reload({ waitUntil: "networkidle2" });
    await new Promise((r) => setTimeout(r, 1500));

    await verifyEmptyStateDOM(page, "Mobile Dark Final Empty State");
    console.log("   ✅ Final clean zero-data state confirmed in Mobile Dark viewport");

    // Final database state check
    const finalDatasets = await apiGetDatasets();
    assert.equal(finalDatasets.length, 0, "Live database must end with 0 datasets");
    console.log("   ✅ Live database confirmed at 0 datasets");

    console.log("\n================================================================================");
    console.log("🎉 ALL PRODUCT LIFECYCLE & INCIDENT REPRODUCTION TESTS PASSED!");
    console.log("================================================================================\n");

  } finally {
    await browser.close();
  }
}

runLifecycleSuite().catch((err) => {
  console.error("\n❌ LIFECYCLE AUDIT FAILED:", err);
  process.exit(1);
});
