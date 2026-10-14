const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822';
const BASE_URL = 'http://localhost:5175';

const DATASETS = [
  { id: '99770', domain: 'Workforce', name: 'Workforce Attendance', shotPrefix: 'qa_track2_2_workforce_dashboard' },
  { id: '99771', domain: 'Retail', name: 'Walmart Store Sales', shotPrefix: 'qa_track2_2_retail_dashboard' },
  { id: '99772', domain: 'Environmental', name: 'CPCB Air Quality', shotPrefix: 'qa_track2_2_environmental_dashboard' }
];

async function runBrowserVerification() {
  console.log('--- Launching Chrome for Track 2.2 Comprehensive Browser Verification (1440 / 1024 / 390) ---');
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const verificationResults = {
    timestamp: new Date().toISOString(),
    desktop_1440: {},
    tablet_1024: {},
    mobile_390: {},
    passed_all: true,
    failures: []
  };

  const viewports = [
    { name: 'desktop', width: 1440, height: 900, key: 'desktop_1440', suffix: '_1440.png' },
    { name: 'tablet', width: 1024, height: 768, key: 'tablet_1024', suffix: '_1024.png' },
    { name: 'mobile', width: 390, height: 844, key: 'mobile_390', suffix: '_390.png' }
  ];

  try {
    for (const vp of viewports) {
      console.log(`\n===============================================================`);
      console.log(`TESTING VIEWPORT: ${vp.name.toUpperCase()} (${vp.width}x${vp.height})`);
      console.log(`===============================================================`);

      for (const ds of DATASETS) {
        console.log(`\nEvaluating Dataset: ${ds.domain} (ID: ${ds.id}) at ${vp.width}px...`);

        const page = await browser.newPage();
        await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 2 });

        const consoleErrors = [];
        page.on('console', msg => {
          if (msg.type() === 'error') {
            const txt = msg.text();
            // Ignore non-blocking resource hints or favicon errors if any
            if (!txt.includes('favicon.ico')) {
              consoleErrors.push(txt);
            }
          }
        });

        const failedRequests = [];
        page.on('requestfailed', request => {
          const err = request.failure()?.errorText || '';
          if (err !== 'net::ERR_ABORTED') {
            failedRequests.push(`${request.method()} ${request.url()} - ${err}`);
          }
        });

        const response = await page.goto(`${BASE_URL}/?dataset_id=${ds.id}#adaptive`, { waitUntil: 'networkidle2', timeout: 35000 });
        if (!response || !response.ok()) {
          verificationResults.failures.push(`[${vp.name} - ${ds.domain}] HTTP navigation status ${response?.status()}`);
        }

        await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
        await new Promise(r => setTimeout(r, 2000));

        // Screenshot
        const shotName = `${ds.shotPrefix}${vp.suffix}`;
        const shotPath = path.join(ARTIFACT_DIR, shotName);
        await page.screenshot({ path: shotPath, fullPage: true });
        console.log(`Captured screenshot: ${shotName}`);

        // Evaluate Card DOM, Layout, and Geometry
        const evaluation = await page.evaluate((dsDomain, vpWidth, vpName) => {
          const errors = [];

          // 1. Horizontal overflow check
          const scrollW = document.documentElement.scrollWidth;
          const innerW = window.innerWidth;
          if (scrollW > innerW + 5) {
            errors.push(`Horizontal overflow detected: scrollWidth ${scrollW}px > window.innerWidth ${innerW}px (+${scrollW - innerW}px)`);
          }

          const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
          const cardDetails = [];
          let totalVisibleWords = 0;

          // 2. Card overlap check
          const rects = cards.map(c => c.getBoundingClientRect());
          for (let i = 0; i < rects.length; i++) {
            for (let j = i + 1; j < rects.length; j++) {
              const r1 = rects[i];
              const r2 = rects[j];
              // Check significant overlap (intersection area > 100px^2)
              const overlapX = Math.max(0, Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left));
              const overlapY = Math.max(0, Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top));
              const overlapArea = overlapX * overlapY;
              if (overlapArea > 200) {
                errors.push(`Card ${i} and Card ${j} overlap spatially by ${Math.round(overlapArea)}px²`);
              }
            }
          }

          cards.forEach((card, idx) => {
            const headingEl = card.querySelector('h3');
            const title = headingEl ? headingEl.textContent.trim() : `Card ${idx}`;
            const titleAttr = headingEl ? headingEl.getAttribute('title') : '';
            const actionBtn = card.querySelector('button[title]');
            const btnTitle = actionBtn ? actionBtn.getAttribute('title') : '';
            
            // 3. Question Title Check
            if (!title.endsWith('?')) {
              errors.push(`Card ${idx} title "${title}" does not end with '?'`);
            }
            if (/chart|plot|heatmap|dumbbell|distribution|correlation/i.test(title)) {
              errors.push(`Card ${idx} title contains chart family jargon: "${title}"`);
            }

            // 4. Technical Title Preservation
            const hasTechnicalTitle = (titleAttr && titleAttr.length > 0) || (btnTitle && btnTitle.length > 0);
            if (!hasTechnicalTitle) {
              errors.push(`Card ${idx} missing technical_title in title or action tooltip`);
            }

            // 5. Primary number check
            const metricEl = card.querySelector('.card-primary-number, .visual-card__metric');
            const metricText = metricEl ? metricEl.textContent.trim() : '';
            if (metricText) {
              if (/^(\d{1,3}(,\d{3})+|\d{4,})$/.test(metricText.replace(/[^\d,]/g, '')) && !/[KMB%µ$r=]/i.test(metricText)) {
                errors.push(`Card ${idx} (${title}) displays raw unformatted count: "${metricText}"`);
              }
            }

            // 6. Title and metric badge overlap check
            if (headingEl && metricEl) {
              const hRect = headingEl.getBoundingClientRect();
              const mRect = metricEl.getBoundingClientRect();
              const overlapX = Math.max(0, Math.min(hRect.right, mRect.right) - Math.max(hRect.left, mRect.left));
              const overlapY = Math.max(0, Math.min(hRect.bottom, mRect.bottom) - Math.max(hRect.top, mRect.top));
              if (overlapX > 0 && overlapY > 0) {
                errors.push(`Card ${idx} (${title}) title heading overlaps with metric badge!`);
              }
            }

            // 7. Visual container size check (no zero-size visuals)
            const chartContainer = card.querySelector('.visual-spec-renderer, .chart-render-container, .echarts-for-react');
            if (chartContainer) {
              const cRect = chartContainer.getBoundingClientRect();
              if (cRect.width <= 10 || cRect.height <= 10) {
                errors.push(`Card ${idx} (${title}) has zero-size or collapsed visual container (${Math.round(cRect.width)}x${Math.round(cRect.height)}px)`);
              }
            }

            // 8. Hero Card dominance check on desktop & tablet
            if (idx === 0 && vpWidth >= 1024) {
              if (chartContainer) {
                const cRect = chartContainer.getBoundingClientRect();
                if (cRect.height < 280) {
                  errors.push(`Hero Card 0 chart height is only ${cRect.height}px (expected >= 280px on ${vpName})`);
                }
              }
            }

            // 9. Finding text & word count
            const findingEl = card.querySelector('.visual-card__finding, .card-finding');
            const findingText = findingEl ? findingEl.textContent.trim() : '';
            if (findingText) {
              const words = findingText.split(/\s+/).filter(Boolean).length;
              totalVisibleWords += words;
            }

            cardDetails.push({
              index: idx,
              title,
              technicalTitle: titleAttr || btnTitle,
              metric: metricText,
              findingText,
              words: findingText ? findingText.split(/\s+/).filter(Boolean).length : 0
            });
          });

          // Check total visible word count
          if (totalVisibleWords > 150) {
            errors.push(`Total visible finding words (${totalVisibleWords}) exceeds budget of 150 words`);
          }

          return {
            cardsCount: cards.length,
            totalVisibleWords,
            cardDetails,
            errors
          };
        }, ds.domain, vp.width, vp.name);

        const allErrors = [...evaluation.errors, ...consoleErrors.map(e => `Console Error: ${e}`), ...failedRequests.map(f => `Failed Request: ${f}`)];

        verificationResults[vp.key][ds.domain] = {
          datasetId: ds.id,
          cardsCount: evaluation.cardsCount,
          totalVisibleWords: evaluation.totalVisibleWords,
          errors: allErrors,
          cardDetails: evaluation.cardDetails
        };

        if (allErrors.length > 0) {
          verificationResults.passed_all = false;
          allErrors.forEach(err => {
            console.error(`  ❌ [${vp.name.toUpperCase()} - ${ds.domain}] ${err}`);
            verificationResults.failures.push(`[${vp.name} - ${ds.domain}] ${err}`);
          });
        } else {
          console.log(`  ✅ [${vp.name.toUpperCase()} - ${ds.domain}] All checks passed! (${evaluation.cardsCount} cards, ${evaluation.totalVisibleWords} words, 0 collisions/overflows)`);
        }

        await page.close();
      }
    }

    const reportPath = path.join(ARTIFACT_DIR, 'qa_track2_2_browser_result.json');
    fs.writeFileSync(reportPath, JSON.stringify(verificationResults, null, 2), 'utf-8');
    console.log(`\nVerification report saved to: ${reportPath}`);

    if (verificationResults.passed_all) {
      console.log(`\n🎉 ALL PRODUCT TRACK 2.2 BROWSER CHECKS PASSED ON 1440, 1024, AND 390 VIEWPORTS!`);
    } else {
      console.error(`\n❌ VERIFICATION FAILED WITH ${verificationResults.failures.length} ERRORS!`);
    }

  } finally {
    await browser.close();
  }
}

runBrowserVerification().catch(err => {
  console.error('Fatal error during browser verification:', err);
  process.exit(1);
});
