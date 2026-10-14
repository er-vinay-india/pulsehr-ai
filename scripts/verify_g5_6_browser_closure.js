const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822';
const BASE_URL = 'http://localhost:5175';

async function runBrowserVerification() {
  console.log('--- Launching Puppeteer with Google Chrome for G5.6 Verification ---');
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const results = {
    viewports: {},
    datasetSwitch: {},
    workforceValidation: {},
    retailValidation: {},
    environmentalValidation: {}
  };

  try {
    const viewports = [
      { name: 'desktop_1440', width: 1440, height: 900, shotName: 'qa_g5_6_desktop_1440.png' },
      { name: 'tablet_1024', width: 1024, height: 768, shotName: 'qa_g5_6_tablet_1024.png' },
      { name: 'mobile_390', width: 390, height: 844, shotName: 'qa_g5_6_mobile_390.png' }
    ];

    for (const vp of viewports) {
      console.log(`\n=== Testing Viewport: ${vp.name} (${vp.width}x${vp.height}) ===`);
      const page = await browser.newPage();
      await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 2 });

      const consoleErrors = [];
      const pageErrors = [];
      const failedRequests = [];

      page.on('console', msg => {
        if (msg.type() === 'error') {
          consoleErrors.push(msg.text());
        }
      });
      page.on('pageerror', err => pageErrors.push(err.message));
      page.on('requestfailed', req => {
        failedRequests.push(`${req.method()} ${req.url()}: ${req.failure()?.errorText}`);
      });

      // Load Workforce dataset 99770
      await page.goto(`${BASE_URL}/?dataset_id=99770#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
      await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
      await new Promise(r => setTimeout(r, 2000));

      const metrics = await page.evaluate(() => {
        const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
        const charts = Array.from(document.querySelectorAll('.executive-visual-card__chart-container, .echarts-for-react, canvas, svg, .podium-wrapper, .matrix-heatmap'));

        // Zero-size charts
        let zeroSizeCount = 0;
        charts.forEach(el => {
          const rect = el.getBoundingClientRect();
          if (rect.width <= 0 || rect.height <= 0) {
            zeroSizeCount++;
          }
        });

        // Check horizontal clipping / overflow on body
        const bodyScrollWidth = document.body.scrollWidth;
        const windowWidth = window.innerWidth;
        const horizontalOverflow = bodyScrollWidth > windowWidth + 2;

        // Check card overlap
        let overlapCount = 0;
        for (let i = 0; i < cards.length; i++) {
          const r1 = cards[i].getBoundingClientRect();
          for (let j = i + 1; j < cards.length; j++) {
            const r2 = cards[j].getBoundingClientRect();
            // Check bounding box intersection
            const xOverlap = Math.max(0, Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left));
            const yOverlap = Math.max(0, Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top));
            if (xOverlap > 5 && yOverlap > 5) {
              overlapCount++;
            }
          }
        }

        // Section breakdown
        const priorityCards = document.querySelectorAll('.executive-insights-grid__priority-zone .executive-visual-card').length;
        const diagnosticCards = document.querySelectorAll('.executive-insights-grid__diagnostic-zone .executive-visual-card').length;
        const supportingCards = document.querySelectorAll('.executive-insights-grid__supporting-zone .executive-visual-card').length;

        return {
          totalCards: cards.length,
          totalCharts: charts.length,
          zeroSizeCharts: zeroSizeCount,
          cardOverlaps: overlapCount,
          horizontalOverflow,
          bodyScrollWidth,
          windowWidth,
          priorityCards,
          diagnosticCards,
          supportingCards
        };
      });

      console.log(`Viewport ${vp.name} metrics:`, metrics);

      // Screenshot to artifacts
      const shotPath = path.join(ARTIFACT_DIR, vp.shotName);
      await page.screenshot({ path: shotPath, fullPage: true });
      console.log(`Saved screenshot to ${shotPath}`);

      results.viewports[vp.name] = {
        metrics,
        consoleErrors,
        pageErrors,
        failedRequests,
        screenshot: shotPath
      };

      await page.close();
    }

    // -------------------------------------------------------------
    // Same-Session Dataset Switch Stress Test:
    // Workforce (99770) -> Retail (99771) -> Environmental (99772) -> Workforce (99770)
    // -------------------------------------------------------------
    console.log('\n=== Testing Same-Session Dataset Switch: Workforce -> Retail -> Environmental -> Workforce ===');
    const switchPage = await browser.newPage();
    await switchPage.setViewport({ width: 1440, height: 900 });

    const switchConsoleErrors = [];
    switchPage.on('console', msg => {
      if (msg.type() === 'error') switchConsoleErrors.push(msg.text());
    });

    const datasetSequence = [
      { id: '99770', domain: 'workforce', name: 'Workforce (Initial)' },
      { id: '99771', domain: 'retail', name: 'Retail' },
      { id: '99772', domain: 'environmental', name: 'Environmental' },
      { id: '99770', domain: 'workforce', name: 'Workforce (Return)' }
    ];

    const sequenceAudit = [];

    for (let step = 0; step < datasetSequence.length; step++) {
      const target = datasetSequence[step];
      console.log(`\nStep ${step + 1}: Navigating to ${target.name} (ID: ${target.id})...`);
      await switchPage.goto(`${BASE_URL}/?dataset_id=${target.id}#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
      await switchPage.waitForSelector('.executive-visual-card', { timeout: 15000 });
      await new Promise(r => setTimeout(r, 2000));

      const pageAudit = await switchPage.evaluate(() => {
        const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
        const cardDetails = cards.map(c => {
          const t = c.querySelector('.executive-visual-card__title, .executive-visual-card__short-title, h4, h3')?.textContent.trim() || '';
          const finding = c.querySelector('.executive-visual-card__finding, p')?.textContent.trim() || '';
          const fullText = c.innerText.toLowerCase();
          return { title: t, finding, fullText };
        });

        const kpis = Array.from(document.querySelectorAll('.kpi-card, .executive-kpi-card')).map(k => k.innerText.toLowerCase());
        const allText = cardDetails.map(c => `${c.title} ${c.finding} ${c.fullText}`).join(' ').toLowerCase();

        return {
          cardCount: cards.length,
          titles: cardDetails.map(c => c.title),
          allCardText: allText,
          kpiCount: kpis.length
        };
      });

      console.log(`Rendered ${pageAudit.cardCount} cards. Titles:`, pageAudit.titles);

      // Domain Isolation Checks
      const violations = [];
      const text = pageAudit.allCardText;

      if (target.domain === 'workforce') {
        if (text.includes('weekly sales') || text.includes('fuel price') || text.includes('temperature') || text.includes('foot traffic') || text.includes('walmart')) {
          violations.push('Retail vocabulary detected in workforce dashboard');
        }
        if (text.includes('pm10') || text.includes('so2') || text.includes('no2') || text.includes('cpcb') || text.includes('air quality')) {
          violations.push('Environmental vocabulary detected in workforce dashboard');
        }
      } else if (target.domain === 'retail') {
        if (text.includes('attendance') || text.includes('leave') || text.includes('wfo') || text.includes('absenteeism')) {
          violations.push('Workforce vocabulary detected in retail dashboard');
        }
        if (text.includes('pm10') || text.includes('so2') || text.includes('no2') || text.includes('cpcb')) {
          violations.push('Environmental vocabulary detected in retail dashboard');
        }
      } else if (target.domain === 'environmental') {
        if (text.includes('attendance') || text.includes('leave') || text.includes('wfo') || text.includes('employee')) {
          violations.push('Workforce vocabulary detected in environmental dashboard');
        }
        if (text.includes('weekly sales') || text.includes('fuel price') || text.includes('walmart') || text.includes('store revenue')) {
          violations.push('Retail vocabulary detected in environmental dashboard');
        }
      }

      sequenceAudit.push({
        step: step + 1,
        target: target.name,
        datasetId: target.id,
        cardCount: pageAudit.cardCount,
        titles: pageAudit.titles,
        kpiCount: pageAudit.kpiCount,
        violationsCount: violations.length,
        violations
      });
    }

    results.datasetSwitch = {
      sequenceAudit,
      switchConsoleErrors
    };

    // -------------------------------------------------------------
    // Explicit Validation: Retail (99771) Scatter, Box Plot, Trend
    // -------------------------------------------------------------
    console.log('\n=== Explicit Verification: Retail (99771) ===');
    await switchPage.goto(`${BASE_URL}/?dataset_id=99771#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
    await switchPage.waitForSelector('.executive-visual-card', { timeout: 15000 });
    await new Promise(r => setTimeout(r, 2000));

    const retailAudit = await switchPage.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
      const cardTexts = cards.map(c => c.innerText.toLowerCase());
      const hasWorkforce = cardTexts.some(t => t.includes('attendance') || t.includes('leave') || t.includes('wfo'));
      const hasRetailScatter = cardTexts.some(t => t.includes('traffic') || t.includes('sales') || t.includes('revenue'));
      return {
        cardCount: cards.length,
        hasWorkforceLeakage: hasWorkforce,
        hasRetailScatter,
        sampleCardTexts: cardTexts.slice(0, 3)
      };
    });
    results.retailValidation = retailAudit;

    // -------------------------------------------------------------
    // Explicit Validation: Environmental (99772) SO2 / NO2 / PM10
    // -------------------------------------------------------------
    console.log('\n=== Explicit Verification: Environmental (99772) ===');
    await switchPage.goto(`${BASE_URL}/?dataset_id=99772#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
    await switchPage.waitForSelector('.executive-visual-card', { timeout: 15000 });
    await new Promise(r => setTimeout(r, 2000));

    const envAudit = await switchPage.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
      const cardTexts = cards.map(c => c.innerText.toLowerCase());
      const hasWorkforce = cardTexts.some(t => t.includes('attendance') || t.includes('leave') || t.includes('wfo') || t.includes('employee'));
      const hasRetail = cardTexts.some(t => t.includes('sales') || t.includes('store') || t.includes('fuel price') || t.includes('revenue'));
      const hasPollutantVisuals = cardTexts.some(t => t.includes('pm10') || t.includes('so2') || t.includes('no2'));
      return {
        cardCount: cards.length,
        hasWorkforceLeakage: hasWorkforce,
        hasRetailLeakage: hasRetail,
        hasPollutantVisuals,
        sampleCardTexts: cardTexts.slice(0, 3)
      };
    });
    results.environmentalValidation = envAudit;

    // -------------------------------------------------------------
    // Explicit Validation: Workforce (99770)
    // -------------------------------------------------------------
    console.log('\n=== Explicit Verification: Workforce (99770) ===');
    await switchPage.goto(`${BASE_URL}/?dataset_id=99770#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
    await switchPage.waitForSelector('.executive-visual-card', { timeout: 15000 });
    await new Promise(r => setTimeout(r, 2000));

    const wfAudit = await switchPage.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
      const cardSummaries = cards.map(c => ({
        title: c.querySelector('.executive-visual-card__title, .executive-visual-card__short-title, h4, h3')?.textContent.trim() || '',
        text: c.innerText
      }));

      const top3Card = cardSummaries.find(c => c.title.includes('Top 3') && (c.title.includes('Employee') || c.title.includes('Attendance Leaders')));
      const deptCard = cardSummaries.find(c => c.title.includes('Department') && c.title.includes('Ranking'));

      return {
        cardCount: cards.length,
        top3EmployeeCardExists: !!top3Card,
        top3EmployeeTitle: top3Card?.title,
        departmentRankingCardExists: !!deptCard,
        departmentRankingTitle: deptCard?.title
      };
    });
    results.workforceValidation = wfAudit;

    await switchPage.close();

  } finally {
    await browser.close();
  }

  console.log('\n--- Final Verification Results ---');
  console.log(JSON.stringify(results, null, 2));
  fs.writeFileSync(path.join(ARTIFACT_DIR, 'qa_g5_6_browser_result.json'), JSON.stringify(results, null, 2));
}

runBrowserVerification().catch(err => {
  console.error('Browser verification failed:', err);
  process.exit(1);
});
