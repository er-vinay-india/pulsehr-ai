const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822';
const BASE_URL = 'http://localhost:5175';

async function runBrowserVerification() {
  console.log('--- Launching Puppeteer with Google Chrome ---');
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
      { name: 'desktop_1440', width: 1440, height: 900, shotName: 'qa_g5_4_desktop_1440.png' },
      { name: 'tablet_1024', width: 1024, height: 768, shotName: 'qa_g5_4_tablet_1024.png' },
      { name: 'mobile_390', width: 390, height: 844, shotName: 'qa_g5_4_mobile_390.png' }
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
        cards.forEach(card => {
          const chartEl = card.querySelector('.executive-visual-card__chart-container') || card;
          const r = chartEl.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) zeroSizeCount++;
        });

        // Horizontal overflow
        const docWidth = document.documentElement.scrollWidth;
        const winWidth = window.innerWidth;
        const hasHorizontalOverflow = docWidth > winWidth + 1;

        // Overlap count between cards
        let overlapCount = 0;
        for (let i = 0; i < cards.length; i++) {
          const r1 = cards[i].getBoundingClientRect();
          for (let j = i + 1; j < cards.length; j++) {
            const r2 = cards[j].getBoundingClientRect();
            const overlap = !(r1.right <= r2.left || r1.left >= r2.right || r1.bottom <= r2.top || r1.top >= r2.bottom);
            if (overlap) overlapCount++;
          }
        }

        // Clipping count
        let clippingCount = 0;
        cards.forEach(card => {
          if (card.scrollHeight > card.clientHeight + 4 || card.scrollWidth > card.clientWidth + 4) {
            clippingCount++;
          }
        });

        const cardTitles = cards.map(c => {
          const el = c.querySelector('.executive-visual-card__title, .executive-visual-card__short-title, h4, h3');
          return el ? el.textContent.trim() : '';
        }).filter(Boolean);

        return {
          cardCount: cards.length,
          chartCount: charts.length,
          zeroSizeCount,
          overlapCount,
          clippingCount,
          hasHorizontalOverflow,
          docWidth,
          winWidth,
          titles: cardTitles
        };
      });

      const shotPath = path.join(ARTIFACT_DIR, vp.shotName);
      await page.screenshot({ path: shotPath, fullPage: false });
      console.log(`Saved screenshot: ${shotPath}`);

      results.viewports[vp.name] = {
        ...metrics,
        consoleErrorCount: consoleErrors.length,
        consoleErrors: consoleErrors.slice(0, 3),
        pageErrorCount: pageErrors.length,
        failedRequestsCount: failedRequests.length
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
          violations.push('Retail leakage in workforce cards');
        }
        if (text.includes('so2') || text.includes('pm10') || text.includes('no2') || text.includes('cpcb') || text.includes('particulate') || text.includes('naaqs')) {
          violations.push('Environmental leakage in workforce cards');
        }
        if (!pageAudit.titles.some(t => t.includes('Attendance') || t.includes('Employee') || t.includes('Department'))) {
          violations.push('Missing expected workforce topics');
        }
      } else if (target.domain === 'retail') {
        if (text.includes('attendance') || text.includes('approved leaves') || text.includes('leave calculation') || text.includes('wfo policy')) {
          violations.push('Workforce leakage in retail cards');
        }
        if (text.includes('so2') || text.includes('pm10') || text.includes('no2') || text.includes('cpcb') || text.includes('particulate')) {
          violations.push('Environmental leakage in retail cards');
        }
        if (!pageAudit.titles.some(t => t.includes('Sales') || t.includes('Store') || t.includes('Revenue') || t.includes('Traffic'))) {
          violations.push('Missing expected retail topics');
        }
      } else if (target.domain === 'environmental') {
        if (text.includes('attendance') || text.includes('approved leaves') || text.includes('wfo') || text.includes('employee attendance')) {
          violations.push('Workforce leakage in environmental cards');
        }
        if (text.includes('weekly sales') || text.includes('fuel price') || text.includes('store sales') || text.includes('retail')) {
          violations.push('Retail leakage in environmental cards');
        }
        if (!pageAudit.titles.some(t => t.includes('PM10') || t.includes('Pollut') || t.includes('SO2') || t.includes('NO2') || t.includes('Air Quality'))) {
          violations.push('Missing expected environmental topics');
        }
      }

      sequenceAudit.push({
        step: step + 1,
        target: target.name,
        cardCount: pageAudit.cardCount,
        titles: pageAudit.titles,
        domainViolations: violations
      });
    }

    results.datasetSwitch = {
      sequenceAudit,
      switchConsoleErrorsCount: switchConsoleErrors.length
    };

    // -------------------------------------------------------------
    // Explicit Validation 7: Retail (99771) Scatter/Relationship
    // Temperature vs Fuel Price / Foot Traffic vs Store Revenue
    // must never carry Attendance/Leave semantics.
    // -------------------------------------------------------------
    console.log('\n=== Explicit Verification: Retail (99771) ===');
    await switchPage.goto(`${BASE_URL}/?dataset_id=99771#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
    await switchPage.waitForSelector('.executive-visual-card', { timeout: 15000 });
    await new Promise(r => setTimeout(r, 2000));

    const retailAudit = await switchPage.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
      const cardTexts = cards.map(c => c.innerText.toLowerCase());
      const hasWorkforce = cardTexts.some(t => t.includes('attendance') || t.includes('leave') || t.includes('wfo'));
      const hasRetailScatter = cardTexts.some(t => (t.includes('traffic') || t.includes('temperature') || t.includes('fuel')) && (t.includes('revenue') || t.includes('sales') || t.includes('association') || t.includes('relationship')));
      return {
        cardCount: cards.length,
        hasWorkforceLeakage: hasWorkforce,
        hasRetailScatter,
        sampleCardTexts: cardTexts.slice(0, 3)
      };
    });
    results.retailValidation = retailAudit;

    // -------------------------------------------------------------
    // Explicit Validation 8: Environmental (99772) SO2 / NO2 / PM10
    // must contain no workforce/retail semantics.
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
    // Explicit Validation 3: Workforce (99770)
    // - Top 3 Employee Attendance Leaders exists
    // - PERSON / podium_top_3
    // - Department ranking exists separately
    // - DEPARTMENT / ranked_bar
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
  fs.writeFileSync('browser_verification_result.json', JSON.stringify(results, null, 2));
}

runBrowserVerification().catch(err => {
  console.error('Browser verification failed:', err);
  process.exit(1);
});
