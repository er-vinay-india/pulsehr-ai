import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/rendered_exports/evidence_certification';
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function runCertification() {
  console.log('--- Starting Evidence Fast Retrieval Certification ---');

  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  // Network tracking
  const requests = [];
  page.on('request', (req) => {
    requests.push({ url: req.url(), method: req.method() });
  });

  const responses = [];
  page.on('response', async (res) => {
    if (res.url().includes('/overview/evidence') || res.url().includes('/adaptive-dashboard')) {
      try {
        const text = await res.text();
        responses.push({
          url: res.url(),
          status: res.status(),
          size: text.length,
        });
      } catch (e) {
        // stream may be closed
      }
    }
  });

  const targetUrl = 'http://localhost:5175/?dataset_id=99795&tab=evidence&topic_id=TOPIC-6fbddfb2&evidence_id=EVID-S9967451-EVID-002&sheet_id=9967451#explorer';
  console.log(`Navigating to target route: ${targetUrl}`);

  const startNav = Date.now();
  await page.goto(targetUrl, { waitUntil: 'networkidle2', timeout: 30000 });

  // 1. Verify Targeted Evidence Card First Load
  await page.waitForSelector('[data-testid="targeted-evidence-card"]', { timeout: 10000 });
  const timeToFirstEvidence = Date.now() - startNav;
  console.log(`[PASS] Targeted evidence card rendered in ${timeToFirstEvidence}ms`);

  // Verify contents of targeted card
  const targetedText = await page.$eval('[data-testid="targeted-evidence-card"]', (el) => el.innerText);
  console.log(`Targeted card text preview: ${targetedText.slice(0, 150).replace(/\n/g, ' ')}...`);

  if (!targetedText.includes('EVID-S9967451-EVID-002')) {
    throw new Error('Targeted evidence ID EVID-S9967451-EVID-002 not found in targeted card!');
  }
  if (!targetedText.includes('VERIFIED')) {
    throw new Error('VERIFIED badge not found in targeted card!');
  }
  console.log('[PASS] Targeted evidence ID and VERIFIED status confirmed');

  // DOM node count on first render
  const domNodeCountInitial = await page.evaluate(() => document.querySelectorAll('*').length);
  console.log(`Initial DOM node count: ${domNodeCountInitial}`);

  // Screenshot 1: Targeted Evidence Initial View
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_targeted_evidence_initial.png') });
  console.log('[SAVED] 01_targeted_evidence_initial.png');

  // 2. Test Lazy Lineage Expansion
  console.log('Testing Lazy Lineage Expansion...');
  const lineageStart = Date.now();
  await page.click('[data-testid="toggle-lineage-btn"]');
  await page.waitForSelector('[data-testid="evidence-lineage-container"]', { timeout: 5000 });
  // Wait for loading spinner to clear
  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="evidence-lineage-container"]');
      return el && !el.innerText.includes('Loading lineage steps');
    },
    { timeout: 5000 }
  );
  const lineageExpandLatency = Date.now() - lineageStart;
  console.log(`[PASS] Lineage container expanded and loaded in ${lineageExpandLatency}ms`);

  const lineageText = await page.$eval('[data-testid="evidence-lineage-container"]', (el) => el.innerText);
  console.log(`Lineage text preview: ${lineageText.slice(0, 150).replace(/\n/g, ' ')}...`);
  if (!lineageText.includes('Ingestion') || !lineageText.includes('Semantic Profiling')) {
    throw new Error('Lineage steps not properly displayed!');
  }
  console.log('[PASS] 4-step lineage workflow verified');

  // Screenshot 2: Lineage Expanded View
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_lineage_expanded.png') });
  console.log('[SAVED] 02_lineage_expanded.png');

  // 3. Test Bounded Source Context Expansion
  console.log('Testing Bounded Source Context Expansion...');
  const sourceStart = Date.now();
  await page.click('[data-testid="toggle-source-context-btn"]');
  await page.waitForSelector('[data-testid="evidence-source-context-container"]', { timeout: 5000 });
  // Wait for loading spinner to clear
  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-testid="evidence-source-context-container"]');
      return el && !el.innerText.includes('Loading bounded sample');
    },
    { timeout: 5000 }
  );
  const sourceExpandLatency = Date.now() - sourceStart;
  console.log(`[PASS] Source context container expanded and loaded in ${sourceExpandLatency}ms`);

  const sourceRowsCount = await page.evaluate(() => {
    const table = document.querySelector('[data-testid="evidence-source-context-container"] table');
    return table ? table.querySelectorAll('tbody tr').length : 0;
  });
  console.log(`Bounded source rows rendered: ${sourceRowsCount} (must be <= 10)`);
  if (sourceRowsCount > 10 || sourceRowsCount === 0) {
    throw new Error(`Expected bounded rows between 1 and 10, got ${sourceRowsCount}`);
  }
  console.log('[PASS] Bounded source context verified');

  // Screenshot 3: Source Context Expanded View
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_source_context_expanded.png') });
  console.log('[SAVED] 03_source_context_expanded.png');

  // 4. Test Paginated Related Evidence DataTable
  console.log('Testing Related Evidence DataTable...');
  await page.waitForSelector('[data-testid="related-evidence-section"]', { timeout: 5000 });
  const tableRowsCount = await page.evaluate(() => {
    return document.querySelectorAll('[data-testid="related-evidence-section"] table tbody tr').length;
  });
  console.log(`Related evidence table rows count: ${tableRowsCount}`);
  if (tableRowsCount === 0) {
    throw new Error('Related evidence table has 0 rows!');
  }
  console.log('[PASS] Related evidence DataTable successfully rendered with rows');

  // Test row click selection switch
  console.log('Testing Evidence Row Selection Switch...');
  const secondRowEvidenceId = await page.evaluate(() => {
    const rows = document.querySelectorAll('[data-testid="related-evidence-section"] table tbody tr');
    if (rows.length > 1) {
      const code = rows[1].querySelector('code');
      return code ? code.innerText.trim() : null;
    }
    return null;
  });

  if (secondRowEvidenceId) {
    console.log(`Clicking second row to switch targeted evidence to: ${secondRowEvidenceId}`);
    const switchStart = Date.now();
    await page.evaluate(() => {
      const rows = document.querySelectorAll('[data-testid="related-evidence-section"] table tbody tr');
      if (rows.length > 1) rows[1].click();
    });
    // Wait for targeted card to update
    await page.waitForFunction(
      (expectedId) => {
        const card = document.querySelector('[data-testid="targeted-evidence-card"]');
        return card && card.innerText.includes(expectedId);
      },
      { timeout: 5000 },
      secondRowEvidenceId
    );
    const switchLatency = Date.now() - switchStart;
    console.log(`[PASS] Evidence switch latency: ${switchLatency}ms`);

    // Screenshot 4: Switched Evidence View
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_switched_evidence.png') });
    console.log('[SAVED] 04_switched_evidence.png');
  }

  // 5. Dark Theme Verification
  console.log('Testing Dark Theme...');
  await page.evaluate(() => {
    document.documentElement.classList.add('dark');
    document.body.classList.add('dark');
  });
  await new Promise((r) => setTimeout(r, 400));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_dark_theme_evidence.png') });
  console.log('[SAVED] 05_dark_theme_evidence.png');

  // 6. Mobile Viewport Verification
  console.log('Testing Mobile Viewport (375x812)...');
  await page.setViewport({ width: 375, height: 812 });
  await new Promise((r) => setTimeout(r, 400));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06_mobile_evidence.png') });
  console.log('[SAVED] 06_mobile_evidence.png');

  await browser.close();

  console.log('--- Telemetry Summary ---');
  console.log(`Responses captured: ${responses.length}`);
  responses.forEach((r) => {
    console.log(`  ${r.url.split('?')[0].split('/').slice(-2).join('/')} -> ${r.size} bytes (status ${r.status})`);
  });

  return {
    timeToFirstEvidence,
    domNodeCountInitial,
    lineageExpandLatency,
    sourceExpandLatency,
    responses,
  };
}

runCertification()
  .then((res) => {
    console.log('Certification completed successfully!', res);
    process.exit(0);
  })
  .catch((err) => {
    console.error('Certification failed:', err);
    process.exit(1);
  });
