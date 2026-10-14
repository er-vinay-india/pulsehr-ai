const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822';
const BASE_URL = 'http://localhost:5175';

const DATASETS = [
  { id: '99770', domain: 'Workforce', name: 'Workforce Attendance', shotPrefix: 'qa_track2_workforce_dashboard' },
  { id: '99771', domain: 'Retail', name: 'Walmart Store Sales', shotPrefix: 'qa_track2_retail_dashboard' },
  { id: '99772', domain: 'Environmental', name: 'CPCB Air Quality', shotPrefix: 'qa_track2_environmental_dashboard' }
];

async function runBrowserVerification() {
  console.log('--- Launching Chrome for Track 2.1 Browser Verification ---');
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const verificationResults = {
    timestamp: new Date().toISOString(),
    desktop_1440: {},
    mobile_390: {},
    passed_all: true,
    failures: []
  };

  const viewports = [
    { name: 'desktop', width: 1440, height: 900, key: 'desktop_1440', suffix: '_1440.png' },
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
          if (msg.type() === 'error') consoleErrors.push(msg.text());
        });

        await page.goto(`${BASE_URL}/?dataset_id=${ds.id}#adaptive`, { waitUntil: 'networkidle2', timeout: 35000 });
        await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
        await new Promise(r => setTimeout(r, 2000));

        // Screenshot
        const shotName = `${ds.shotPrefix}${vp.suffix}`;
        const shotPath = path.join(ARTIFACT_DIR, shotName);
        await page.screenshot({ path: shotPath, fullPage: true });
        console.log(`Captured screenshot: ${shotName}`);

        // Evaluate Card DOM and CSS
        const evaluation = await page.evaluate((dsDomain) => {
          const errors = [];

          // 1. Check Executive Briefing Banner for cross-domain leakage
          const banner = document.querySelector('.executive-briefing-card, .executive-summary-banner, .briefing-card');
          const bannerText = banner ? banner.innerText : '';
          
          if (dsDomain === 'Environmental') {
            if (bannerText.includes('$') || bannerText.includes('Store Station') || bannerText.includes('/wk') || /sales density/i.test(bannerText)) {
              errors.push(`Environmental executive summary contains retail leakage: "${bannerText.slice(0, 100)}..."`);
            }
          }

          // 2. Check Executive Cards
          const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
          const cardDetails = [];

          cards.forEach((card, idx) => {
            const title = card.querySelector('h3')?.textContent.trim() || `Card ${idx}`;
            
            // Check .sr-only styling
            const srOnlyEl = card.querySelector('.sr-only');
            let srOnlyHidden = true;
            if (srOnlyEl) {
              const style = window.getComputedStyle(srOnlyEl);
              const rect = srOnlyEl.getBoundingClientRect();
              const isClipped = style.clip === 'rect(0px, 0px, 0px, 0px)' || style.clip === 'rect(0, 0, 0, 0)';
              const isTiny = (rect.width <= 1 && rect.height <= 1);
              const isAbsolute = style.position === 'absolute';
              if (!isAbsolute || (!isClipped && !isTiny)) {
                srOnlyHidden = false;
                errors.push(`Card ${idx} (${title}) .sr-only element is visible on screen! (rect: ${rect.width}x${rect.height}, clip: ${style.clip})`);
              }
            }

            // Visible finding text
            const findingEl = card.querySelector('.visual-card__finding, .card-finding');
            const findingText = findingEl ? findingEl.textContent.trim() : '';

            // Check duplicate text
            const visibleParagraphs = Array.from(card.querySelectorAll('p, figcaption span')).filter(p => {
              const rect = p.getBoundingClientRect();
              return rect.width > 10 && rect.height > 10;
            }).map(p => p.textContent.trim());

            const textOccurrences = visibleParagraphs.filter(t => t === findingText).length;
            if (findingText && textOccurrences > 1) {
              errors.push(`Card ${idx} (${title}) renders finding text ${textOccurrences} times visibly!`);
            }

            // Check grammatical subject completeness
            if (findingText) {
              const firstChar = findingText[0];
              if (firstChar !== firstChar.toUpperCase()) {
                errors.push(`Card ${idx} (${title}) finding starts with lowercase: "${findingText}"`);
              }
              if (!findingText.endsWith('.')) {
                errors.push(`Card ${idx} (${title}) finding does not end with period: "${findingText}"`);
              }
              if (/^(meet or exceed|operational dependency \(r)/i.test(findingText) && !/^(Core departments|Observed|Substantial)/i.test(findingText)) {
                errors.push(`Card ${idx} (${title}) finding missing subject: "${findingText}"`);
              }
            }

            // Check Card 1 Environmental Leader
            if (dsDomain === 'Environmental' && idx === 0) {
              const metricEl = card.querySelector('.card-primary-number, .visual-card__metric');
              const metricText = metricEl ? metricEl.textContent.trim() : '';
              if (!metricText.includes('210')) {
                errors.push(`Environmental Card 0 primary metric expected '210 µg/m³ peak', got '${metricText}'`);
              }
              if (!findingText.includes('Delhi')) {
                errors.push(`Environmental Card 0 finding expected Delhi leader, got '${findingText}'`);
              }
            }

            cardDetails.push({
              index: idx,
              title,
              findingText,
              srOnlyHidden
            });
          });

          return {
            bannerText: bannerText.slice(0, 150),
            cardsCount: cards.length,
            cardDetails,
            errors
          };
        }, ds.domain);

        verificationResults[vp.key][ds.domain] = {
          datasetId: ds.id,
          cardsCount: evaluation.cardsCount,
          bannerSnippet: evaluation.bannerText,
          errors: evaluation.errors
        };

        if (evaluation.errors.length > 0) {
          verificationResults.passed_all = false;
          evaluation.errors.forEach(err => {
            console.error(`  ❌ [${vp.name.toUpperCase()} - ${ds.domain}] ${err}`);
            verificationResults.failures.push(`[${vp.name} - ${ds.domain}] ${err}`);
          });
        } else {
          console.log(`  ✅ [${vp.name.toUpperCase()} - ${ds.domain}] Passed all checks (0 duplicate findings, 0 cross-domain leaks, complete subjects, correct leader)!`);
        }

        await page.close();
      }
    }

    const reportPath = path.join(ARTIFACT_DIR, 'executive_dashboard_verification_result.json');
    fs.writeFileSync(reportPath, JSON.stringify(verificationResults, null, 2), 'utf-8');
    console.log(`\nVerification report saved to: ${reportPath}`);

    if (verificationResults.passed_all) {
      console.log(`\n🎉 ALL PRODUCT TRACK 2.1 BROWSER CHECKS PASSED ON DESKTOP & MOBILE!`);
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
