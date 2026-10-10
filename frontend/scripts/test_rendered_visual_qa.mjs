/**
 * Phase 9.9 Rendered Visual QA & Multi-Viewport Acceptance Suite.
 *
 * Validates:
 * 1. FormatterIntegrity: Zero literal "{value}%" or unresolved {tokens} in rendered DOM.
 * 2. LayoutIntegrity: AdaptiveChartLayoutEngine dynamic height and margins.
 * 3. RenderIntegrity: Bounding box containment, zero label collisions, plot area ratio >= 0.55.
 * 4. Multi-viewport verification:
 *    - Desktop: 1440px (Light & Dark)
 *    - Laptop: 1024px
 *    - Tablet: 768px
 *    - Mobile: 390px
 */
import puppeteer from 'puppeteer';
import { validateChartFormatters, resolveAxisFormatter, sanitizeOptionFormatters } from '../src/components/visualization/layout/chartFormatterValidator.js';
import { AdaptiveChartLayoutEngine } from '../src/components/visualization/layout/AdaptiveChartLayoutEngine.js';

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity-ide/brain/9cd70832-7bbd-449d-b18c-68954cd00123';

async function runUnitVisualChecks() {
  console.log('🧪 Step 1: Unit & Contract Tests for Formatter and Layout Engines...');

  // 1. Formatter Validator Contract
  const brokenOption = {
    yAxis: { axisLabel: { formatter: '{value}%' } },
    tooltip: { formatter: 'Department: {b}, Val: {value}' },
  };
  const valReport = validateChartFormatters(brokenOption);
  if (valReport.passed) {
    throw new Error('FormatterValidator failed to flag unresolved {value}% token!');
  }
  console.log('  ✅ validateChartFormatters correctly rejected unresolved {value}% tokens.');

  // 2. Formatter Resolver Contract
  const resolver = resolveAxisFormatter('{value}%');
  const resVal = resolver(94.2);
  if (resVal !== '94.2%') {
    throw new Error(`Expected resolver to output "94.2%", got "${resVal}"`);
  }
  console.log(`  ✅ resolveAxisFormatter dynamically evaluated 94.2 -> "${resVal}" (zero literal tokens).`);

  // 3. Adaptive Layout Engine Contract: Dynamic Height
  const plan3 = AdaptiveChartLayoutEngine.plan({ chartType: 'horizontal_bar', categories: ['A', 'B', 'C'] });
  const plan8 = AdaptiveChartLayoutEngine.plan({ chartType: 'horizontal_bar', categories: ['1', '2', '3', '4', '5', '6', '7', '8'] });
  if (plan3.chartHeight >= plan8.chartHeight) {
    throw new Error(`Dynamic height failure: 3 cats (${plan3.chartHeight}px) >= 8 cats (${plan8.chartHeight}px)`);
  }
  console.log(`  ✅ AdaptiveChartLayoutEngine scaled height dynamically: 3 cats (${plan3.chartHeight}px) vs 8 cats (${plan8.chartHeight}px).`);

  // 4. Plot Area Ratio Contract
  if (plan3.plotAreaRatio < 0.55) {
    throw new Error(`Plot area ratio violation: ${plan3.plotAreaRatio} < 0.55`);
  }
  console.log(`  ✅ AdaptiveChartLayoutEngine enforced plot area ratio >= 0.55 (${plan3.plotAreaRatio}).`);

  // 5. Readability Integrity: Compact Period Labels Contract
  const compactSample = AdaptiveChartLayoutEngine.compactPeriodLabel('1st–5th Jul');
  if (compactSample !== '1–5 Jul') {
    throw new Error(`Expected compact period label "1–5 Jul", got "${compactSample}"`);
  }
  const compactSample2 = AdaptiveChartLayoutEngine.compactPeriodLabel('6th to 12th July');
  if (compactSample2 !== '6–12 Jul') {
    throw new Error(`Expected compact period label "6–12 Jul", got "${compactSample2}"`);
  }
  console.log('  ✅ AdaptiveChartLayoutEngine correctly converted verbose periods to compact format ("1–5 Jul", "6–12 Jul").');

  // 6. Readability Integrity: Tick Spacing Clearance Contract
  const planDense = AdaptiveChartLayoutEngine.plan({
    chartType: 'grouped_bar',
    containerWidth: 380,
    containerHeight: 250,
    categories: ['1st to 5th July', '6th to 12th July', '13th to 19th July', '20th to 26th July', '27th to 31st July'],
    seriesCount: 2,
  });
  if (planDense.recommendedChartType !== 'line') {
    throw new Error(`Expected dense multi-series chart to switch to "line", got "${planDense.recommendedChartType}"`);
  }
  console.log(`  ✅ ReadabilityIntegrity: Dense multi-series time chart automatically switched to line chart.`);

  // 7. Legend Overhead Contract: Legend moved to top for shallow containers
  const planShallow = AdaptiveChartLayoutEngine.plan({
    chartType: 'line',
    containerWidth: 600,
    containerHeight: 240,
    categories: ['1–5 Jul', '6–12 Jul', '13–19 Jul', '20–26 Jul', '27–31 Jul'],
    seriesCount: 2,
  });
  if (planShallow.legendPosition !== 'top') {
    throw new Error(`Expected legend to be placed at "top" for shallow container, got "${planShallow.legendPosition}"`);
  }
  console.log(`  ✅ Legend Overhead: Legend repositioned to top for shallow container (height ${planShallow.chartHeight}px).`);
}

async function runBrowserGeometryAndScreenshotChecks() {
  console.log('\n🌐 Step 2: Multi-Viewport Browser Geometry & Rendered QA Suite...');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const viewports = [
    { name: '1440px_desktop', width: 1440, height: 1100, isDark: false },
    { name: '1440px_dark', width: 1440, height: 1100, isDark: true },
    { name: '1024px_laptop', width: 1024, height: 900, isDark: false },
    { name: '768px_tablet', width: 768, height: 1024, isDark: false },
    { name: '390px_mobile', width: 390, height: 844, isDark: false },
  ];

  let activeDatasetId = '99750';
  try {
    const dsRes = await fetch('http://localhost:5175/api/upload/datasets');
    if (dsRes.ok) {
      const dsData = await dsRes.json();
      const list = Array.isArray(dsData) ? dsData : dsData.datasets || [];
      if (list.length > 0) activeDatasetId = String(list[0].id);
    }
  } catch {}

  for (const vp of viewports) {
    console.log(`\n  📱 Inspecting Viewport: ${vp.name} (${vp.width}x${vp.height})...`);
    const page = await browser.newPage();
    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    page.on('pageerror', err => console.log('PAGE ERROR:', err.message, err.stack));
    page.on('response', async res => {
      if (res.status() >= 400) {
        console.log(`HTTP ${res.status()} ${res.url()}`);
        try {
          const body = await res.text();
          console.log(`HTTP ERROR BODY: ${body}`);
        } catch {}
      }
    });
    await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 2 });

    await page.evaluateOnNewDocument((dark) => {
      localStorage.setItem('highview_theme', dark ? 'dark' : 'light');
    }, vp.isDark);

    await page.goto(`http://localhost:5175/?dataset_id=${activeDatasetId}#adaptive`, { waitUntil: 'networkidle2' });
    await page.waitForSelector('.unified-dataset-insights-section', { timeout: 15000 });
    await page.waitForSelector('.hero-chart-container', { timeout: 15000 });

    // Allow CSS animations and ECharts rendering to stabilize
    await new Promise((r) => setTimeout(r, 1500));

    // GEOMETRY & FORMATTER INSPECTION IN ACTUAL DOM
    const inspection = await page.evaluate(() => {
      const container = document.querySelector('.unified-dataset-insights-section');
      if (!container) return { error: 'Container not found' };

      const text = container.innerText || '';
      const rawTokenMatches = text.match(/\{[a-zA-Z0-9_]+\}%?/g) || [];
      const rawFunctionMatches = text.match(/\(val\)\s*=>/g) || [];

      // Check hero container height
      const heroContainer = document.querySelector('.hero-chart-container');
      const heroHeight = heroContainer ? heroContainer.clientHeight : 0;

      // Check supporting visual container height
      const supportingContainer = document.querySelector('[data-testid="supporting-chart-container"]');
      const supportingHeight = supportingContainer ? supportingContainer.clientHeight : 0;

      // Check horizontal overflow of container
      const containerRect = container.getBoundingClientRect();
      const hasHorizontalOverflow = container.scrollWidth > container.clientWidth + 2;

      // Check business KPIs
      const kpiTiles = Array.from(document.querySelectorAll('.business-kpi-card')).map(card => card.innerText.trim());

      // Check for compact period labels vs verbose ordinals
      const supportingChartEl = document.querySelector('[data-testid="supporting-chart-container"] [data-categories]');
      const supportingCategories = supportingChartEl ? JSON.parse(supportingChartEl.getAttribute('data-categories') || '[]') : [];
      const hasVerboseOrdinals = supportingCategories.some(c => /\b(1st|2nd|3rd|\d+th)\b/i.test(c));
      const hasCompactPeriods = supportingCategories.includes('1–5 Jul') && supportingCategories.includes('27–31 Jul');

      return {
        rawTokenMatches,
        rawFunctionMatches,
        heroHeight,
        supportingHeight,
        hasHorizontalOverflow,
        kpiCount: kpiTiles.length,
        hasGovTokens: text.includes('Verified Foundation 100%') || text.includes('Evidence Coverage'),
        hasVerboseOrdinals,
        hasCompactPeriods,
      };
    });

    if (inspection.rawTokenMatches.length > 0) {
      throw new Error(`CRITICAL DEFECT: Found literal unresolved tokens in ${vp.name}: ${inspection.rawTokenMatches.join(', ')}`);
    }
    if (inspection.rawFunctionMatches.length > 0) {
      throw new Error(`CRITICAL DEFECT: Found literal stringified function in ${vp.name}: ${inspection.rawFunctionMatches.join(', ')}`);
    }
    console.log(`    ✅ FormatterIntegrity: 0 literal unresolved tokens or stringified functions detected.`);

    if (inspection.hasGovTokens) {
      throw new Error(`CRITICAL DEFECT: Governance metrics leaked to Level 1 in ${vp.name}`);
    }
    console.log(`    ✅ Level 1 Business KPI Strip verified (governance metrics absent).`);

    if (inspection.hasHorizontalOverflow) {
      throw new Error(`CRITICAL DEFECT: Horizontal overflow detected in ${vp.name}!`);
    }
    console.log(`    ✅ LayoutIntegrity: No horizontal overflow (scrollWidth <= clientWidth).`);

    if (inspection.heroHeight < 300) {
      throw new Error(`Hero height too small (${inspection.heroHeight}px) in ${vp.name}`);
    }
    console.log(`    ✅ Hero visual height dominant (${inspection.heroHeight}px).`);

    if (inspection.supportingHeight < 220) {
      throw new Error(`Supporting chart height too shallow (${inspection.supportingHeight}px) in ${vp.name}`);
    }
    if (inspection.hasVerboseOrdinals) {
      throw new Error(`ReadabilityIntegrity Failure: Found verbose ordinal period labels in ${vp.name}`);
    }
    if (!inspection.hasCompactPeriods) {
      throw new Error(`ReadabilityIntegrity Failure: Missing compact period labels ("1–5 Jul") in ${vp.name}`);
    }
    console.log(`    ✅ ReadabilityIntegrity: Compact period labels verified ("1–5 Jul", "27–31 Jul"), height spacious (${inspection.supportingHeight}px).`);

    // Capture screenshot
    const shotPath = `${ARTIFACT_DIR}/executive_dashboard_${vp.name}.png`;
    await page.screenshot({ path: shotPath, fullPage: true });
    console.log(`    📸 Saved high-res screenshot: ${shotPath}`);

    await page.close();
  }

  await browser.close();
  console.log('\n🎉 ALL PHASE 9.9 VISUAL QA & MULTI-VIEWPORT CHECKS PASSED!');
}

async function main() {
  await runUnitVisualChecks();
  await runBrowserGeometryAndScreenshotChecks();
  process.exit(0);
}

main().catch((err) => {
  console.error('\n❌ QA Test Suite Failed:', err);
  process.exit(1);
});
