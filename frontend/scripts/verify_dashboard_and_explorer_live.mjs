import puppeteer from 'puppeteer';

const BASE_URL = 'http://localhost:5175';
const BACKEND_URL = 'http://localhost:8000';
const DATASET_ID = '99767';

async function main() {
  console.log('🚀 Starting Dashboard & Data Explorer Browser Verification...');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 2 });

  const consoleLogs = [];
  const networkErrors = [];
  const apiRequests = [];

  page.on('console', msg => {
    const text = msg.text();
    const type = msg.type();
    consoleLogs.push({ type, text });
    if (type === 'error' || type === 'warning') {
      console.log(`[Browser ${type.toUpperCase()}]: ${text}`);
    }
  });

  page.on('requestfailed', req => {
    networkErrors.push({
      url: req.url(),
      failure: req.failure()?.errorText || 'unknown'
    });
    console.log(`[Network FAILED]: ${req.url()} (${req.failure()?.errorText})`);
  });

  page.on('response', res => {
    const url = res.url();
    if (url.includes('/api/')) {
      apiRequests.push({
        url,
        status: res.status(),
        ok: res.ok()
      });
      if (!res.ok()) {
        console.log(`[API ERROR ${res.status()}]: ${url}`);
      }
    }
  });

  // ==========================================
  // PART 1: DASHBOARD VERIFICATION
  // ==========================================
  console.log('\n--- 1. Testing Dashboard ---');
  await page.goto(`${BASE_URL}/?dataset_id=${DATASET_ID}#dashboard`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 2000));

  const dashboardState = await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('.executive-visual-card')).map(el => {
      const title = el.querySelector('h3, .card-title, .visual-card-title')?.innerText?.trim();
      const hasChart = !!el.querySelector('.echarts-for-react, svg, canvas');
      return { title, hasChart };
    });

    const sections = Array.from(document.querySelectorAll('.dashboard-section, section')).map(sec => ({
      title: sec.querySelector('h2, .section-title')?.innerText?.trim(),
      cardCount: sec.querySelectorAll('.executive-visual-card').length
    }));

    const datasetSelector = document.querySelector('select, [role="combobox"]')?.innerText?.trim() || '';

    return {
      cardCount: cards.length,
      cards,
      sections,
      datasetSelector,
      bodyTextSnippet: document.body.innerText.slice(0, 300)
    };
  });

  console.log(`Dashboard Cards rendered: ${dashboardState.cardCount}`);
  dashboardState.cards.forEach((c, idx) => {
    console.log(`  Card ${idx + 1}: "${c.title}" (Chart rendered: ${c.hasChart})`);
  });

  const dashboardScreenshot = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/live_dashboard_check.png';
  await page.screenshot({ path: dashboardScreenshot, fullPage: false });
  console.log(`📸 Dashboard screenshot saved to ${dashboardScreenshot}`);

  // ==========================================
  // PART 2: DATA EXPLORER TABS VERIFICATION
  // ==========================================
  console.log('\n--- 2. Testing Data Explorer ---');
  const tabsToTest = [
    'overview',
    'rankings',
    'relationships',
    'evidence',
    'technical'
  ];

  for (const tab of tabsToTest) {
    console.log(`\nNavigating to Data Explorer tab: [${tab}]`);
    await page.goto(`${BASE_URL}/?dataset_id=${DATASET_ID}&tab=${tab}#explorer`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 1500));

    const tabState = await page.evaluate(currentTab => {
      const activeNavTab = document.querySelector('.explorer-nav-tab--active, [data-active="true"], button.active')?.innerText?.trim();
      const tables = document.querySelectorAll('table, .data-table, .tabular-grid').length;
      const charts = document.querySelectorAll('.echarts-for-react, svg, canvas').length;
      const errorBoxes = Array.from(document.querySelectorAll('.error-box, .alert-error, .error-message')).map(e => e.innerText.trim());
      const pageTitle = document.querySelector('h1, h2')?.innerText?.trim();

      return {
        activeNavTab,
        tables,
        charts,
        errorBoxes,
        pageTitle,
        hasContent: document.body.innerText.length > 500
      };
    }, tab);

    console.log(`  Tab [${tab}] loaded:`);
    console.log(`    Page Title: "${tabState.pageTitle}"`);
    console.log(`    Tables found: ${tabState.tables}, Charts found: ${tabState.charts}`);
    console.log(`    Has substantial content: ${tabState.hasContent}`);
    if (tabState.errorBoxes.length > 0) {
      console.log(`    ⚠️ Error boxes: ${tabState.errorBoxes.join('; ')}`);
    }

    const tabScreenshot = `/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/live_explorer_${tab}_check.png`;
    await page.screenshot({ path: tabScreenshot, fullPage: false });
    console.log(`  📸 Screenshot saved to live_explorer_${tab}_check.png`);
  }

  // Summary
  console.log('\n==========================================');
  console.log('VERIFICATION SUMMARY:');
  console.log(`Total API Requests captured: ${apiRequests.length}`);
  const failedApis = apiRequests.filter(r => !r.ok);
  console.log(`Failed API Requests: ${failedApis.length}`);
  failedApis.forEach(r => console.log(`  ❌ ${r.status}: ${r.url}`));

  console.log(`Total Network Load Failures: ${networkErrors.length}`);
  networkErrors.forEach(e => console.log(`  ❌ ${e.url} (${e.failure})`));

  const severeConsoleErrors = consoleLogs.filter(l => l.type === 'error');
  console.log(`Severe Console Errors: ${severeConsoleErrors.length}`);
  severeConsoleErrors.forEach(e => console.log(`  ❌ [Console Error]: ${e.text}`));

  await browser.close();
  console.log('\n✅ Verification script completed.');
}

main().catch(err => {
  console.error('Fatal execution error in verification:', err);
  process.exit(1);
});
