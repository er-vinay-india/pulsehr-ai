const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822';
const BASE_URL = 'http://localhost:5175';

const DATASETS = [
  { id: '99770', domain: 'Workforce', name: 'Workforce Attendance', shotPrefix: 'qa_track2_3_workforce_dashboard' },
  { id: '99771', domain: 'Retail', name: 'Walmart Store Sales', shotPrefix: 'qa_track2_3_retail_dashboard' },
  { id: '99772', domain: 'Environmental', name: 'CPCB Air Quality', shotPrefix: 'qa_track2_3_environmental_dashboard' }
];

const VIEWPORTS = [
  { name: 'desktop_1440', width: 1440, height: 900, suffix: '_1440.png' },
  { name: 'tablet_1024', width: 1024, height: 768, suffix: '_1024.png' },
  { name: 'tablet_768', width: 768, height: 1024, suffix: '_768.png' },
  { name: 'mobile_390', width: 390, height: 844, suffix: '_390.png' }
];

async function runTrack23BrowserVerification() {
  console.log('=== PRODUCT TRACK 2.3: MANDATORY 12-STATE BROWSER VERIFICATION MATRIX ===\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const verificationResults = {
    timestamp: new Date().toISOString(),
    viewports: VIEWPORTS.map(v => v.name),
    states: {},
    passed_all: true,
    total_states_evaluated: 0,
    total_states_passed: 0,
    failures: []
  };

  try {
    for (const vp of VIEWPORTS) {
      console.log(`\n===============================================================`);
      console.log(`EVALUATING VIEWPORT: ${vp.name.toUpperCase()} (${vp.width}x${vp.height})`);
      console.log(`===============================================================`);
      verificationResults.states[vp.name] = {};

      for (const ds of DATASETS) {
        verificationResults.total_states_evaluated++;
        console.log(`\nTesting [${vp.name} - ${ds.domain} (ID: ${ds.id})]...`);

        const page = await browser.newPage();
        await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 2 });

        const consoleErrors = [];
        page.on('console', msg => {
          if (msg.type() === 'error' && !msg.text().includes('favicon.ico')) {
            consoleErrors.push(msg.text());
          }
        });

        const pageErrors = [];
        page.on('pageerror', err => {
          pageErrors.push(err.message || String(err));
        });

        const failedRequests = [];
        page.on('requestfailed', request => {
          const err = request.failure()?.errorText || '';
          if (err !== 'net::ERR_ABORTED') {
            failedRequests.push(`${request.method()} ${request.url()} - ${err}`);
          }
        });

        const startTime = Date.now();
        const response = await page.goto(`${BASE_URL}/?dataset_id=${ds.id}#adaptive`, {
          waitUntil: 'networkidle2',
          timeout: 35000
        });

        if (!response || !response.ok()) {
          verificationResults.failures.push(`[${vp.name} - ${ds.domain}] HTTP navigation status ${response?.status()}`);
        }

        await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
        await new Promise(r => setTimeout(r, 1500));
        const renderOverheadMs = Date.now() - startTime;

        // Screenshot
        const shotName = `${ds.shotPrefix}${vp.suffix}`;
        const shotPath = path.join(ARTIFACT_DIR, shotName);
        await page.screenshot({ path: shotPath, fullPage: true });
        console.log(`  📸 Captured screenshot: ${shotName}`);

        // Evaluate Card Geometry, Spatial Polish, Axis, Legends, and Controls
        const evaluation = await page.evaluate((vpWidth, vpHeight, isDesktop, isTablet, isMobile) => {
          const errors = [];
          const scrollW = document.documentElement.scrollWidth;
          const innerW = window.innerWidth;
          const horizontalOverflow = Math.max(0, scrollW - innerW);

          if (scrollW > innerW + 5) {
            errors.push(`Horizontal overflow detected: scrollWidth ${scrollW}px > window.innerWidth ${innerW}px (+${horizontalOverflow}px)`);
          }

          const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
          let zeroSizeCharts = 0;
          let overlaps = 0;
          let clipping = 0;

          // 1. Card-to-card spatial overlap check
          const rects = cards.map(c => c.getBoundingClientRect());
          for (let i = 0; i < rects.length; i++) {
            for (let j = i + 1; j < rects.length; j++) {
              const r1 = rects[i];
              const r2 = rects[j];
              const overlapX = Math.max(0, Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left));
              const overlapY = Math.max(0, Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top));
              const overlapArea = overlapX * overlapY;
              if (overlapArea > 150) {
                overlaps++;
                errors.push(`Card ${i} and Card ${j} overlap spatially by ${Math.round(overlapArea)}px²`);
              }
            }
          }

          const cardDetails = [];

          cards.forEach((card, idx) => {
            const cardRect = card.getBoundingClientRect();
            if (cardRect.right > vpWidth + 5 || cardRect.left < -5) {
              clipping++;
              errors.push(`Card ${idx} clipped outside viewport bounds (x: ${Math.round(cardRect.left)} to ${Math.round(cardRect.right)})`);
            }

            const headingEl = card.querySelector('h3');
            const headingRect = headingEl ? headingEl.getBoundingClientRect() : null;
            const title = headingEl ? headingEl.textContent.trim() : `Card ${idx}`;

            const metricEl = card.querySelector('.card-primary-number, .visual-card__metric');
            const metricRect = metricEl ? metricEl.getBoundingClientRect() : null;

            const actionsEl = card.querySelector('.visual-card__actions-cell');
            const actionsRect = actionsEl ? actionsEl.getBoundingClientRect() : null;

            // 2. Action Controls vs Title Collision check
            if (headingRect && actionsRect) {
              const overlapX = Math.max(0, Math.min(headingRect.right, actionsRect.right) - Math.max(headingRect.left, actionsRect.left));
              const overlapY = Math.max(0, Math.min(headingRect.bottom, actionsRect.bottom) - Math.max(headingRect.top, actionsRect.top));
              if (overlapX > 0 && overlapY > 0) {
                overlaps++;
                errors.push(`Card ${idx} (${title}): Actions cell overlaps with title heading`);
              }
            }

            // 3. Title vs Metric Collision check
            if (headingRect && metricRect) {
              const overlapX = Math.max(0, Math.min(headingRect.right, metricRect.right) - Math.max(headingRect.left, metricRect.left));
              const overlapY = Math.max(0, Math.min(headingRect.bottom, metricRect.bottom) - Math.max(headingRect.top, metricRect.top));
              if (overlapX > 0 && overlapY > 0) {
                overlaps++;
                errors.push(`Card ${idx} (${title}): Heading overlaps with primary metric badge`);
              }
            }

            // 4. Visual container & Canvas verification
            const chartContainer = card.querySelector('.visual-spec-renderer, .chart-render-container, .podium-top-3-container');
            const canvasEl = card.querySelector('canvas');
            const canvasRect = canvasEl ? canvasEl.getBoundingClientRect() : null;
            const containerRect = chartContainer ? chartContainer.getBoundingClientRect() : null;

            const cWidth = canvasRect ? canvasRect.width : (containerRect ? containerRect.width : 0);
            const cHeight = canvasRect ? canvasRect.height : (containerRect ? containerRect.height : 0);

            if (cWidth <= 15 || cHeight <= 15) {
              zeroSizeCharts++;
              errors.push(`Card ${idx} (${title}): Zero-size or collapsed visual container (${Math.round(cWidth)}x${Math.round(cHeight)}px)`);
            }

            // 5. Hero dominance check on Desktop & Tablet
            if (idx === 0 && (isDesktop || isTablet)) {
              if (cHeight < 280) {
                errors.push(`Hero Card 0 (${title}): Chart canvas height is ${Math.round(cHeight)}px (must be >= 280px for visual dominance)`);
              }
            }

            cardDetails.push({
              index: idx,
              title,
              span: card.getAttribute('data-column-span') || '12',
              card_width: Math.round(cardRect.width),
              card_height: Math.round(cardRect.height),
              canvas_width: Math.round(cWidth),
              canvas_height: Math.round(cHeight)
            });
          });

          return {
            cardsCount: cards.length,
            zeroSizeCharts,
            overlaps,
            clipping,
            horizontalOverflow,
            cardDetails,
            errors
          };
        }, vp.width, vp.height, vp.name === 'desktop_1440', vp.name.startsWith('tablet'), vp.name === 'mobile_390');

        const allErrors = [
          ...evaluation.errors,
          ...consoleErrors.map(e => `Console Error: ${e}`),
          ...pageErrors.map(e => `Page Error: ${e}`),
          ...failedRequests.map(f => `Failed Request: ${f}`)
        ];

        const stateReport = {
          viewport: vp.name,
          width: vp.width,
          height: vp.height,
          dataset: ds.domain,
          dataset_id: ds.id,
          cards_rendered: evaluation.cardsCount,
          chart_containers: evaluation.cardsCount,
          zero_size_charts: evaluation.zeroSizeCharts,
          overlaps: evaluation.overlaps,
          clipping: evaluation.clipping,
          horizontal_overflow_px: evaluation.horizontalOverflow,
          console_errors_count: consoleErrors.length,
          page_errors_count: pageErrors.length,
          failed_requests_count: failedRequests.length,
          render_overhead_ms: renderOverheadMs,
          card_details: evaluation.cardDetails,
          passed: allErrors.length === 0,
          errors: allErrors
        };

        verificationResults.states[vp.name][ds.domain] = stateReport;

        if (stateReport.passed) {
          verificationResults.total_states_passed++;
          console.log(`  ✅ [PASS] 0 zero-size, 0 overlaps, 0 clipping, 0 overflow, 0 errors (${renderOverheadMs}ms)`);
        } else {
          verificationResults.passed_all = false;
          console.error(`  ❌ [FAIL] ${allErrors.length} errors:`);
          allErrors.forEach(e => console.error(`     - ${e}`));
          verificationResults.failures.push(`[${vp.name} - ${ds.domain}]: ${allErrors.join('; ')}`);
        }

        await page.close();
      }
    }

    const reportPath = path.join(ARTIFACT_DIR, 'qa_track2_3_browser_matrix_result.json');
    fs.writeFileSync(reportPath, JSON.stringify(verificationResults, null, 2), 'utf-8');
    console.log(`\n===============================================================`);
    console.log(`Track 2.3 Browser Matrix Saved to: ${reportPath}`);
    console.log(`States Passed: ${verificationResults.total_states_passed} / ${verificationResults.total_states_evaluated}`);
    if (verificationResults.passed_all) {
      console.log(`🎉 ALL 12 BROWSER MATRIX STATES PASSED CLEANLY (100%)!`);
    } else {
      console.error(`❌ Matrix verification encountered failures!`);
    }

  } finally {
    await browser.close();
  }
}

runTrack23BrowserVerification().catch(err => {
  console.error('Fatal error during Track 2.3 verification:', err);
  process.exit(1);
});
