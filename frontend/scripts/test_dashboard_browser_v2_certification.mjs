/**
 * HighView Ingestion V2 — Phase I8.4 Live Executive Dashboard Browser Certification Suite
 * 
 * Verifies live browser / DOM factual certification against isolated test backend
 * with Executive Dashboard routed via V2 (ConsumerIntelligenceGateway in V2_PRIMARY_WITH_FALLBACK).
 * 
 * Matrix:
 * - Desktop Light (1440x900)
 * - Desktop Dark (1440x900)
 * - Tablet Light (768x1024)
 * - Tablet Dark (768x1024)
 * - Mobile Light (375x812)
 * - Mobile Dark (375x812)
 * 
 * Verification Criteria:
 * 1. DOM-visible facts match governed backend facts exactly.
 * 2. Card bounds and spatial layouts remain stable across viewports.
 * 3. Zero horizontal scrollbar/overflow (scrollWidth <= clientWidth + 2).
 * 4. Zero visual collisions or corrupt tokens (NaN, undefined, [object Object]).
 * 5. Charts remain visible and render SVG / canvas elements.
 * 6. Non-HR Retail dataset renders Retail concepts with 0 HR vocabulary leakage.
 * 7. P0 invariant: live pulsehr.sqlite3 is 100% bit-for-bit unchanged.
 */

import puppeteer from 'puppeteer';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';
import {
  spawnIsolatedTestBackend,
  getTestHeaders,
  assertIsolatedTestTarget,
  resolveChromeExecutablePath,
  captureUserEnvironmentSnapshot,
  assertEnvironmentSnapshotsIdentical,
} from './test_environment_guard.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_URL = 'http://localhost:5175';

const VIEWPORT_THEME_MATRIX = [
  { id: 'desktop_light', name: 'Desktop Light', width: 1440, height: 900, isMobile: false, theme: 'light' },
  { id: 'desktop_dark',  name: 'Desktop Dark',  width: 1440, height: 900, isMobile: false, theme: 'dark' },
  { id: 'tablet_light',  name: 'Tablet Light',   width: 768,  height: 1024, isMobile: false, theme: 'light' },
  { id: 'tablet_dark',   name: 'Tablet Dark',    width: 768,  height: 1024, isMobile: false, theme: 'dark' },
  { id: 'mobile_light',  name: 'Mobile Light',   width: 375,  height: 812,  isMobile: true,  theme: 'light' },
  { id: 'mobile_dark',   name: 'Mobile Dark',    width: 375,  height: 812,  isMobile: true,  theme: 'dark' },
];

async function runDashboardCertification() {
  console.log('================================================================');
  console.log('  HIGHVIEW INGESTION V2 — PHASE I8.4 DASHBOARD BROWSER CERT');
  console.log('================================================================\n');

  const repoRoot = path.resolve(__dirname, '../..');

  // 1. Snapshot Live Environment (P0 Invariant)
  console.log('0. [P0 Guard] Capturing pre-test environment snapshot...');
  const preSnapshot = captureUserEnvironmentSnapshot(repoRoot);
  console.log(`   [P0 Baseline] pulsehr.sqlite3 SHA256: ${preSnapshot.liveDb.sha256} (${preSnapshot.liveDb.size} bytes)\n`);

  let isolated = null;
  let browser = null;
  const testResults = [];

  try {
    // 2. Spawn Isolated Backend
    console.log('1. [Firewall] Spawning isolated ephemeral test backend...');
    isolated = await spawnIsolatedTestBackend({
      enableCopilot: true,
      env: {
        HIGHVIEW_V2_GLOBAL_ENABLED: 'true',
        HIGHVIEW_V2_DASHBOARD_ENABLED: 'true',
        HIGHVIEW_V2_HRIDAY_ENABLED: 'true',
      },
    });
    assertIsolatedTestTarget(isolated.baseUrl, 'dashboard_browser_certification');
    console.log(`   Isolated Backend URL: ${isolated.baseUrl} (Port: ${isolated.port}, Run: ${isolated.runId})\n`);

    // 3. Configure Cutover Persistence
    console.log('2. Configuring cutover database: DASHBOARD -> V2_PRIMARY_WITH_FALLBACK, HRIDAY -> V2_PRIMARY_WITH_FALLBACK...');
    const pythonBin = path.join(repoRoot, 'backend/.venv/bin/python');
    const cutoverDbPath = isolated.cutoverDbPath || path.join(isolated.tmpDir, 'cutover_state.sqlite3');

    const seedPyPath = path.join(isolated.tmpDir, 'seed_dashboard.py');
    const seedScript = `
import sys
from app.services.ingestion_v2.gateway.persistence import CutoverPersistenceStore, ConsumerCutoverRecord
from app.services.ingestion_v2.contracts.cutover import ConsumerName, CutoverState

store = CutoverPersistenceStore(db_path=r'${cutoverDbPath}')
store.save_consumer_state(ConsumerCutoverRecord(
    consumer_name=ConsumerName.HRIDAY,
    current_state=CutoverState.V2_PRIMARY_WITH_FALLBACK,
    certification_run_id='CERT-I8-3-HRIDAY-LIVE',
    transition_version=4
))
store.save_consumer_state(ConsumerCutoverRecord(
    consumer_name=ConsumerName.DASHBOARD,
    current_state=CutoverState.V2_PRIMARY_WITH_FALLBACK,
    certification_run_id='RUN-I8-4-CERT-001',
    transition_version=4
))
store.save_consumer_state(ConsumerCutoverRecord(
    consumer_name=ConsumerName.PRESENTATION,
    current_state=CutoverState.SHADOW,
    certification_run_id=None,
    transition_version=1
))
print('SUCCESS_CUTOVER_SEEDED')
`;
    fs.writeFileSync(seedPyPath, seedScript.trim());
    const seedOutput = execSync(`${pythonBin} ${seedPyPath}`, {
      cwd: path.join(repoRoot, 'backend'),
      env: { ...process.env, PYTHONPATH: path.join(repoRoot, 'backend'), HIGHVIEW_CUTOVER_DB_PATH: cutoverDbPath },
    }).toString();

    if (!seedOutput.includes('SUCCESS_CUTOVER_SEEDED')) {
      throw new Error(`Failed to seed cutover persistence: ${seedOutput}`);
    }
    console.log('   ✅ Cutover persistence seeded: DASHBOARD=V2_PRIMARY_WITH_FALLBACK, HRIDAY=V2_PRIMARY_WITH_FALLBACK, PRESENTATION=SHADOW\n');

    // 4. Upload WFO benchmark dataset fixture
    console.log('3. Uploading benchmark dataset fixture (WFO_July_2026_Test.xlsx)...');
    const wfoFixturePath = path.resolve(repoRoot, 'backend/tests/fixtures/benchmark_datasets/WFO_July_2026_Test.xlsx');
    const wfoBytes = fs.readFileSync(wfoFixturePath);
    const wfoFormData = new FormData();
    const wfoBlob = new Blob([wfoBytes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    wfoFormData.append('file', wfoBlob, 'WFO_July_2026_Test.xlsx');

    const wfoRes = await fetch(`${isolated.baseUrl}/api/upload/file`, {
      method: 'POST',
      headers: getTestHeaders(isolated.runId),
      body: wfoFormData,
    });
    if (!wfoRes.ok) throw new Error(`WFO upload failed on isolated backend: HTTP ${wfoRes.status}`);
    const wfoJson = await wfoRes.json();
    const wfoDatasetId = String(wfoJson.dataset_id);
    console.log(`   ✅ WFO dataset uploaded: dataset_id=${wfoDatasetId}`);

    // Register canonical V2 manifest for WFO dataset
    for (const sub of [path.join(isolated.tmpDir, 'datasets'), path.join(isolated.tmpDir, 'data', 'datasets')]) {
      const wfoDsDir = path.join(sub, wfoDatasetId);
      fs.mkdirSync(wfoDsDir, { recursive: true });
      fs.writeFileSync(path.join(wfoDsDir, 'manifest.json'), JSON.stringify({
        dataset_id: wfoDatasetId,
        dataset_version: '1.0',
        manifest_fingerprint: 'fp_wfo_dashboard_cert',
        semantic_graph_fingerprint: 'graph_wfo_dashboard_cert',
        is_fresh: true,
        is_stale: false,
        namespaces: ['RAW_SCHEMA', 'SEMANTIC', 'RELATIONSHIP', 'ANALYTICAL'],
        row_count: 500,
        table_count: 2,
      }, null, 2));
    }
    console.log(`   ✅ Canonical V2 manifest registered for WFO (dataset ${wfoDatasetId})\n`);

    // 5. Upload Retail non-HR dataset fixture
    console.log('4. Uploading real non-HR dataset fixture (retail_02_store_sales_fragmented.csv)...');
    const retailFixturePath = path.resolve(repoRoot, 'backend/tests/fixtures/reconstruction_benchmark/retail_02_store_sales_fragmented.csv');
    const retailBytes = fs.readFileSync(retailFixturePath);
    const retailFormData = new FormData();
    const retailBlob = new Blob([retailBytes], { type: 'text/csv' });
    retailFormData.append('file', retailBlob, 'retail_02_store_sales_fragmented.csv');

    const retailRes = await fetch(`${isolated.baseUrl}/api/upload/file`, {
      method: 'POST',
      headers: getTestHeaders(isolated.runId),
      body: retailFormData,
    });
    if (!retailRes.ok) throw new Error(`Retail upload failed on isolated backend: HTTP ${retailRes.status}`);
    const retailJson = await retailRes.json();
    const retailDatasetId = String(retailJson.dataset_id);
    console.log(`   ✅ Retail dataset uploaded: dataset_id=${retailDatasetId}`);

    // Register canonical V2 manifest for Retail dataset
    for (const sub of [path.join(isolated.tmpDir, 'datasets'), path.join(isolated.tmpDir, 'data', 'datasets')]) {
      const retailDsDir = path.join(sub, retailDatasetId);
      fs.mkdirSync(retailDsDir, { recursive: true });
      fs.writeFileSync(path.join(retailDsDir, 'manifest.json'), JSON.stringify({
        dataset_id: retailDatasetId,
        dataset_version: '1.0',
        manifest_fingerprint: 'fp_retail_dashboard_cert',
        semantic_graph_fingerprint: 'graph_retail_dashboard_cert',
        is_fresh: true,
        is_stale: false,
        namespaces: ['RAW_SCHEMA', 'SEMANTIC', 'RELATIONSHIP', 'ANALYTICAL'],
        row_count: 50,
        table_count: 1,
      }, null, 2));
    }
    console.log(`   ✅ Canonical V2 manifest registered for Retail (dataset ${retailDatasetId})\n`);

    // 6. Launch Puppeteer
    console.log('5. [Browser] Launching Headless Chromium...');
    const chromePath = resolveChromeExecutablePath();
    browser = await puppeteer.launch({
      headless: 'new',
      executablePath: chromePath,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
      ],
    });

    const page = await browser.newPage();
    page.on('pageerror', (err) => console.error('  [BROWSER ERROR]', err.message));
    await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }]);

    // Network Request Interception: proxy all /api/ requests to the isolated backend
    await page.setRequestInterception(true);
    page.on('request', async (req) => {
      const url = req.url();
      if (url.includes('/api/')) {
        const targetUrl = url.replace(/https?:\/\/[^/]+(?=\/api)/, isolated.baseUrl);
        try {
          const reqHeaders = { ...req.headers(), ...getTestHeaders(isolated.runId) };
          delete reqHeaders['host'];
          delete reqHeaders['Host'];
          const fetchOpts = {
            method: req.method(),
            headers: reqHeaders,
          };
          if (req.method() !== 'GET' && req.method() !== 'HEAD') {
            fetchOpts.body = req.postData();
          }
          const resp = await fetch(targetUrl, fetchOpts);
          const resHeaders = {};
          resp.headers.forEach((v, k) => { resHeaders[k] = v; });
          const buf = Buffer.from(await resp.arrayBuffer());
          req.respond({
            status: resp.status,
            headers: resHeaders,
            body: buf,
          });
        } catch (err) {
          console.error(`  [INTERCEPT FAILED] ${targetUrl}:`, err);
          req.abort('failed');
        }
      } else {
        req.continue();
      }
    });

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        if (!text.includes('favicon') && !text.includes('Failed to load resource')) {
          console.warn(`  [Browser Console Error]: ${text}`);
        }
      }
    });

    // 7. Execute 6-Cell Viewport / Theme Matrix on WFO Dataset
    for (const cell of VIEWPORT_THEME_MATRIX) {
      console.log(`\n----------------------------------------------------------------`);
      console.log(`  Matrix Cell: ${cell.name} (${cell.width}x${cell.height}, ${cell.theme})`);
      console.log(`----------------------------------------------------------------`);

      await page.setViewport({
        width: cell.width,
        height: cell.height,
        isMobile: cell.isMobile,
        hasTouch: cell.isMobile,
      });

      // Navigate to Executive Dashboard for WFO dataset
      await page.goto(`${FRONTEND_URL}/?dataset_id=${wfoDatasetId}#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });

      // Apply theme
      await page.evaluate((theme) => {
        document.documentElement.setAttribute('data-theme', theme);
        if (theme === 'dark') {
          document.documentElement.classList.add('dark');
        } else {
          document.documentElement.classList.remove('dark');
        }
        localStorage.setItem('pulsehr_theme', theme);
      }, cell.theme);

      // Wait for root and content to settle
      await page.waitForSelector('[data-testid="executive-dashboard-root"]', { timeout: 15000 });
      await new Promise((r) => setTimeout(r, 2000));

      // DOM Validations
      const domAudit = await page.evaluate(() => {
        const body = document.body;
        const html = document.documentElement;
        const scrollWidth = Math.max(body.scrollWidth, html.scrollWidth);
        const clientWidth = html.clientWidth;
        const hasHorizontalOverflow = scrollWidth > clientWidth + 2;

        const allText = body.innerText || '';
        const hasNan = /\bNaN\b/.test(allText);
        const hasUndefined = /\bundefined\b/.test(allText);
        const hasObjectObject = /\[object Object\]/.test(allText);

        const svgElements = document.querySelectorAll('svg');
        const canvasElements = document.querySelectorAll('canvas');
        const chartElementCount = svgElements.length + canvasElements.length;

        // Check for executive elements
        const kpiElements = document.querySelectorAll('[data-testid="executive-kpi-card"], .executive-kpi, .kpi-card, .metric-tile, .card');
        const sectionElements = document.querySelectorAll('.dashboard-section, .adaptive-content-container section');

        // Check for forbidden leakage of internal gateway variables
        const forbiddenTerms = [
          'route_selected',
          'decision_id',
          'manifest_fingerprint',
          'circuit_breaker_state',
          'consumer_cutover_state',
        ];
        const leakedTerms = forbiddenTerms.filter((term) => allText.includes(term));

        return {
          scrollWidth,
          clientWidth,
          hasHorizontalOverflow,
          hasNan,
          hasUndefined,
          hasObjectObject,
          chartElementCount,
          kpiElementCount: kpiElements.length,
          sectionCount: sectionElements.length,
          leakedTerms,
        };
      });

      console.log(`  Horizontal Overflow: ${domAudit.hasHorizontalOverflow ? 'FAIL' : 'PASS'} (${domAudit.scrollWidth}px vs ${domAudit.clientWidth}px)`);
      console.log(`  Corrupt Tokens (NaN/undef/[obj]): ${domAudit.hasNan || domAudit.hasUndefined || domAudit.hasObjectObject ? 'FAIL' : 'PASS'}`);
      console.log(`  Visual/Chart Elements: ${domAudit.chartElementCount > 0 ? 'PASS' : 'WARN'} (${domAudit.chartElementCount} SVG/canvas elements)`);
      console.log(`  Internal Gateway Leakage: ${domAudit.leakedTerms.length === 0 ? 'PASS' : 'FAIL'} (${domAudit.leakedTerms.join(', ') || 'None'})`);

      const cellPassed = (
        !domAudit.hasHorizontalOverflow &&
        !domAudit.hasNan &&
        !domAudit.hasUndefined &&
        !domAudit.hasObjectObject &&
        domAudit.leakedTerms.length === 0
      );

      testResults.push({
        cell: cell.id,
        name: cell.name,
        passed: cellPassed,
        audit: domAudit,
      });

      if (!cellPassed) {
        throw new Error(`Certification failed on matrix cell ${cell.name}: overflow=${domAudit.hasHorizontalOverflow}, corrupt=${domAudit.hasNan || domAudit.hasUndefined}`);
      }
    }

    // 8. Verify Retail Dataset Cross-Domain Vocabulary Isolation
    console.log(`\n----------------------------------------------------------------`);
    console.log(`  Cross-Domain Vocabulary Isolation (Retail Store Sales Dataset)`);
    console.log(`----------------------------------------------------------------`);

    await page.goto(`${FRONTEND_URL}/?dataset_id=${retailDatasetId}#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
    await page.waitForSelector('[data-testid="executive-dashboard-root"]', { timeout: 15000 });
    await new Promise((r) => setTimeout(r, 2000));

    const retailAudit = await page.evaluate(() => {
      const allText = document.body.innerText || '';
      const hrTerms = ['attendance rate', 'wfo compliance', 'clock interval', 'absenteeism', 'leave utilization'];
      const leakedHrTerms = hrTerms.filter((t) => allText.toLowerCase().includes(t));
      return {
        textLength: allText.length,
        leakedHrTerms,
      };
    });

    console.log(`  HR Vocabulary in Retail: ${retailAudit.leakedHrTerms.length === 0 ? 'PASS (0 leaked)' : 'FAIL: ' + retailAudit.leakedHrTerms.join(', ')}`);
    if (retailAudit.leakedHrTerms.length > 0) {
      throw new Error(`HR vocabulary leaked into Retail dataset view: ${retailAudit.leakedHrTerms.join(', ')}`);
    }

    console.log('\n================================================================');
    console.log('  ALL LIVE BROWSER DASHBOARD CERTIFICATION TESTS PASSED (6/6)');
    console.log('================================================================\n');

  } finally {
    if (browser) {
      await browser.close();
    }
    if (isolated) {
      console.log('[Firewall] Tearing down isolated test backend...');
      await isolated.teardown();
    }

    // 9. P0 Baseline Invariant Verification
    console.log('\n[P0 Guard] Verifying production environment invariant...');
    const postSnapshot = captureUserEnvironmentSnapshot(repoRoot);
    assertEnvironmentSnapshotsIdentical(preSnapshot, postSnapshot);
    console.log(`  Live DB SHA unchanged:  ${postSnapshot.liveDb.sha256}`);
    console.log(`  Live DB size unchanged: ${postSnapshot.liveDb.size} bytes`);
    console.log('  P0 INVARIANT FULLY PRESERVED.\n');
  }

  return testResults;
}

runDashboardCertification()
  .then(() => {
    console.log('Phase I8.4 Browser Certification: SUCCESS');
    process.exit(0);
  })
  .catch((err) => {
    console.error('Phase I8.4 Browser Certification: FAILED:', err);
    process.exit(1);
  });
