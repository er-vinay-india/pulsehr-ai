const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822';
const BASE_URL = 'http://localhost:5175';

const DATASETS = [
  { id: '99770', domain: 'Workforce', name: 'Workforce Attendance', shotName: 'qa_track2_workforce_dashboard_1440.png' },
  { id: '99771', domain: 'Retail', name: 'Walmart Store Sales', shotName: 'qa_track2_retail_dashboard_1440.png' },
  { id: '99772', domain: 'Environmental', name: 'CPCB Air Quality', shotName: 'qa_track2_environmental_dashboard_1440.png' }
];

async function runDashboardAudit() {
  console.log('--- Launching Chrome for Executive Dashboard Quality Audit (Track 2) ---');
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const auditReport = {
    timestamp: new Date().toISOString(),
    datasets: {}
  };

  try {
    for (const ds of DATASETS) {
      console.log(`\n===============================================================`);
      console.log(`Auditing Dataset: ${ds.name} (ID: ${ds.id})`);
      console.log(`===============================================================`);

      const page = await browser.newPage();
      await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

      const consoleErrors = [];
      page.on('console', msg => {
        if (msg.type() === 'error') consoleErrors.push(msg.text());
      });

      await page.goto(`${BASE_URL}/?dataset_id=${ds.id}#adaptive`, { waitUntil: 'networkidle2', timeout: 30000 });
      await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
      // Allow charts and animations to settle
      await new Promise(r => setTimeout(r, 2500));

      // Capture screenshot
      const shotPath = path.join(ARTIFACT_DIR, ds.shotName);
      await page.screenshot({ path: shotPath, fullPage: true });
      console.log(`Saved screenshot: ${ds.shotName}`);

      // Detailed DOM extraction
      const pageData = await page.evaluate(() => {
        // 1. Briefing Banner / Executive Summary
        const banner = document.querySelector('.executive-briefing-card, .executive-summary-banner, .briefing-card');
        const bannerText = banner ? banner.innerText.trim() : '';

        // 2. Executive KPIs
        const kpiEls = Array.from(document.querySelectorAll('.kpi-card, .executive-kpi-card, .executive-kpi-grid > div'));
        const kpis = kpiEls.map(el => {
          const label = el.querySelector('.kpi-label, .text-xs, h5, span')?.textContent.trim() || '';
          const value = el.querySelector('.kpi-value, .text-xl, .text-2xl, strong, .font-bold')?.textContent.trim() || '';
          return { label, value, raw: el.innerText.trim().replace(/\n+/g, ' ') };
        });

        // 3. Section Headers
        const sections = Array.from(document.querySelectorAll('.section-header, .executive-insights-grid__section-title, h2, h3'))
          .map(s => s.textContent.trim())
          .filter(t => t.length > 0);

        // 4. Executive Visual Cards
        const cardEls = Array.from(document.querySelectorAll('.executive-visual-card'));
        const cards = cardEls.map((c, idx) => {
          const isHero = c.classList.contains('hero-card') || c.classList.contains('visual-card--hero');
          const colSpan = c.getAttribute('data-column-span') || (isHero ? '8' : '4');
          const title = c.querySelector('.visual-card__title, h3, h4')?.textContent.trim() || '';
          const primaryNumber = c.querySelector('.card-primary-number, .visual-card__metric')?.textContent.trim() || '';
          const shortContext = c.querySelector('.card-short-context, .visual-card__context')?.textContent.trim() || '';
          const finding = c.querySelector('.visual-card__finding, .card-short-insight p, figcaption p')?.textContent.trim() || '';
          const fullText = c.innerText.trim();

          // Chart inspection
          const chartContainer = c.querySelector('.echarts-for-react, canvas, svg, .executive-visual-card__chart-container, figure');
          const chartRect = chartContainer ? chartContainer.getBoundingClientRect() : null;
          const hasCanvas = !!c.querySelector('canvas');
          const hasSvg = !!c.querySelector('svg');

          // Word counts and readability metrics
          const titleWords = title.split(/\s+/).filter(Boolean).length;
          const findingWords = finding.split(/\s+/).filter(Boolean).length;
          const totalWords = fullText.split(/\s+/).filter(Boolean).length;

          // Question-based title check (starts with Who, Which, What, How, Where, Does, Is or contains '?')
          const isQuestionTitle = /^(who|which|what|how|where|does|is|are|why)\b/i.test(title) || title.includes('?');

          // Units presence in title or metric
          const hasUnitsInHeader = /(%|days|staff|rate|usd|\$|ppm|ug\/m3|sales|count|records|ratio)/i.test(title + ' ' + primaryNumber + ' ' + shortContext);

          // Ranking direction indicator in title or finding
          const hasDirectionInText = /(highest|lowest|top|bottom|worst|best|leading|lagging|decrease|increase|growth)/i.test(title + ' ' + finding);

          return {
            index: idx + 1,
            isHero,
            colSpan: parseInt(colSpan, 10),
            title,
            primaryNumber,
            shortContext,
            finding,
            titleWords,
            findingWords,
            totalWords,
            isQuestionTitle,
            hasUnitsInHeader,
            hasDirectionInText,
            chartSize: chartRect ? { width: Math.round(chartRect.width), height: Math.round(chartRect.height) } : null,
            hasCanvas,
            hasSvg,
            fullTextSnippet: fullText.substring(0, 150).replace(/\n+/g, ' ')
          };
        });

        // 5. Total Prose on Page
        const totalPageWords = cards.reduce((sum, c) => sum + c.totalWords, 0) + bannerText.split(/\s+/).filter(Boolean).length;
        const totalReadingSeconds = Math.round((totalPageWords / 200) * 60);

        return {
          bannerSnippet: bannerText.substring(0, 200).replace(/\n+/g, ' '),
          kpis,
          sections,
          cards,
          totalCards: cards.length,
          heroCardCount: cards.filter(c => c.isHero).length,
          totalPageWords,
          totalReadingSeconds
        };
      });

      auditReport.datasets[ds.domain] = {
        name: ds.name,
        datasetId: ds.id,
        screenshot: shotPath,
        consoleErrors,
        ...pageData
      };

      console.log(`Audited ${pageData.cards.length} cards, ${pageData.kpis.length} KPIs. Total page words: ${pageData.totalPageWords} (~${pageData.totalReadingSeconds}s reading time).`);
      await page.close();
    }

    const reportPath = path.join(ARTIFACT_DIR, 'executive_dashboard_audit_result.json');
    fs.writeFileSync(reportPath, JSON.stringify(auditReport, null, 2));
    console.log(`\nWritten full audit result to ${reportPath}`);

  } finally {
    await browser.close();
  }
}

runDashboardAudit().catch(err => {
  console.error('Audit failed:', err);
  process.exit(1);
});
