const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822';
const BASE_URL = 'http://localhost:5175';

const DATASETS = [
  { id: '99770', domain: 'Workforce', name: 'Workforce Attendance' },
  { id: '99771', domain: 'Retail', name: 'Walmart Store Sales' },
  { id: '99772', domain: 'Environmental', name: 'CPCB Air Quality' }
];

const VIEWPORTS = [
  { name: 'desktop_1440', width: 1440, height: 900 },
  { name: 'tablet_1024', width: 1024, height: 768 },
  { name: 'tablet_768', width: 768, height: 1024 },
  { name: 'mobile_390', width: 390, height: 844 }
];

async function captureBaseline() {
  console.log('=== PRODUCT TRACK 2.3: BASELINE GEOMETRY & RENDERING CAPTURE ===\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const baselineData = {
    captured_at: new Date().toISOString(),
    viewports: VIEWPORTS,
    datasets: DATASETS,
    records: {}
  };

  try {
    for (const vp of VIEWPORTS) {
      console.log(`--- Viewport: ${vp.name.toUpperCase()} (${vp.width}x${vp.height}) ---`);
      baselineData.records[vp.name] = {};

      for (const ds of DATASETS) {
        console.log(`  Capturing: ${ds.domain} (ID: ${ds.id})...`);
        const page = await browser.newPage();
        await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 2 });

        const consoleErrors = [];
        page.on('console', msg => {
          if (msg.type() === 'error' && !msg.text().includes('favicon.ico')) {
            consoleErrors.push(msg.text());
          }
        });

        const response = await page.goto(`${BASE_URL}/?dataset_id=${ds.id}#adaptive`, {
          waitUntil: 'networkidle2',
          timeout: 35000
        });

        await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
        await new Promise(r => setTimeout(r, 2000));

        // Evaluate baseline geometry
        const measurement = await page.evaluate((vpWidth, vpHeight) => {
          const scrollWidth = document.documentElement.scrollWidth;
          const dashboardEl = document.querySelector('.adaptive-dashboard-view, main, body');
          const dashboardHeight = dashboardEl ? dashboardEl.getBoundingClientRect().height : document.documentElement.scrollHeight;

          const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
          let zeroSizeChartCount = 0;
          let overlapCount = 0;
          let clippingCount = 0;

          // 1. Overlap detection
          const cardRects = cards.map(c => c.getBoundingClientRect());
          for (let i = 0; i < cardRects.length; i++) {
            for (let j = i + 1; j < cardRects.length; j++) {
              const r1 = cardRects[i];
              const r2 = cardRects[j];
              const overlapX = Math.max(0, Math.min(r1.right, r2.right) - Math.max(r1.left, r2.left));
              const overlapY = Math.max(0, Math.min(r1.bottom, r2.bottom) - Math.max(r1.top, r2.top));
              if (overlapX * overlapY > 100) {
                overlapCount++;
              }
            }
          }

          const cardRecords = cards.map((card, idx) => {
            const cardRect = card.getBoundingClientRect();
            if (cardRect.right > vpWidth + 5 || cardRect.left < -5) {
              clippingCount++;
            }

            const headingEl = card.querySelector('h3');
            const headingRect = headingEl ? headingEl.getBoundingClientRect() : null;

            const metricEl = card.querySelector('.card-primary-number, .visual-card__metric');
            const metricRect = metricEl ? metricEl.getBoundingClientRect() : null;

            const spanAttr = card.getAttribute('data-column-span');
            const span = spanAttr ? parseInt(spanAttr, 10) : 12;

            // Chart container and canvas
            const chartContainer = card.querySelector('.visual-spec-renderer, .chart-render-container, .podium-top-3-container');
            const canvasEl = card.querySelector('canvas');
            const canvasRect = canvasEl ? canvasEl.getBoundingClientRect() : null;
            const containerRect = chartContainer ? chartContainer.getBoundingClientRect() : null;

            if (containerRect && (containerRect.width <= 10 || containerRect.height <= 10)) {
              zeroSizeChartCount++;
            }

            // Topic ID and title
            const idAttr = headingEl ? headingEl.getAttribute('id') : '';
            const topicId = idAttr ? idAttr.replace('topic-title-', '') : `topic_${idx}`;
            const title = headingEl ? headingEl.textContent.trim() : '';

            // Try to extract ECharts instance info
            let chartType = 'unknown';
            let legendBounds = null;
            let axisBounds = null;

            const echartDom = card.querySelector('div[_echarts_instance_]');
            if (echartDom && window.echarts) {
              try {
                const instance = window.echarts.getInstanceByDom(echartDom);
                if (instance) {
                  const opt = instance.getOption();
                  if (opt) {
                    if (opt.series && opt.series[0]) {
                      chartType = opt.series[0].type || 'echarts';
                    }
                    if (opt.legend && opt.legend[0] && opt.legend[0].show !== false) {
                      legendBounds = {
                        show: true,
                        top: opt.legend[0].top,
                        right: opt.legend[0].right,
                        bottom: opt.legend[0].bottom,
                        left: opt.legend[0].left,
                        orient: opt.legend[0].orient || 'horizontal'
                      };
                    }
                    if (opt.grid && opt.grid[0]) {
                      axisBounds = {
                        top: opt.grid[0].top,
                        right: opt.grid[0].right,
                        bottom: opt.grid[0].bottom,
                        left: opt.grid[0].left,
                        containLabel: opt.grid[0].containLabel
                      };
                    }
                  }
                }
              } catch (e) {
                // Ignore extraction error
              }
            } else if (card.querySelector('.podium-top-3-container')) {
              chartType = 'podium_top_3';
            }

            // Estimate grid row and col based on position
            return {
              index: idx,
              topic_id: topicId,
              title,
              chart_type: chartType,
              span,
              rendered_width: Math.round(cardRect.width),
              rendered_height: Math.round(cardRect.height),
              card_bounds: {
                x: Math.round(cardRect.x),
                y: Math.round(cardRect.y),
                width: Math.round(cardRect.width),
                height: Math.round(cardRect.height)
              },
              chart_canvas_width: canvasRect ? Math.round(canvasRect.width) : (containerRect ? Math.round(containerRect.width) : 0),
              chart_canvas_height: canvasRect ? Math.round(canvasRect.height) : (containerRect ? Math.round(containerRect.height) : 0),
              title_height: headingRect ? Math.round(headingRect.height) : 0,
              metric_badge_bounds: metricRect ? {
                x: Math.round(metricRect.x),
                y: Math.round(metricRect.y),
                width: Math.round(metricRect.width),
                height: Math.round(metricRect.height)
              } : null,
              legend_bounds: legendBounds,
              axis_bounds: axisBounds
            };
          });

          return {
            page_scroll_width: scrollWidth,
            viewport_width: vpWidth,
            dashboard_total_height: Math.round(dashboardHeight),
            number_of_cards: cards.length,
            zero_size_chart_count: zeroSizeChartCount,
            overlap_count: overlapCount,
            clipping_count: clippingCount,
            card_records: cardRecords
          };
        }, vp.width, vp.height);

        measurement.console_errors = consoleErrors;
        baselineData.records[vp.name][ds.domain] = measurement;

        console.log(`    -> Cards: ${measurement.number_of_cards}, Zero-size: ${measurement.zero_size_chart_count}, Overlaps: ${measurement.overlap_count}, Overflow: ${measurement.page_scroll_width > vp.width ? measurement.page_scroll_width - vp.width : 0}px`);

        await page.close();
      }
    }

    const baselinePath = path.join(ARTIFACT_DIR, 'track2_3_baseline_geometry.json');
    fs.writeFileSync(baselinePath, JSON.stringify(baselineData, null, 2), 'utf-8');
    console.log(`\n✅ Product Track 2.3 baseline recorded to: ${baselinePath}`);

  } finally {
    await browser.close();
  }
}

captureBaseline().catch(err => {
  console.error('Fatal error during baseline capture:', err);
  process.exit(1);
});
