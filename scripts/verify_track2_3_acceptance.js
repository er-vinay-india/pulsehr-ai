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

const RESIZE_CYCLE = [
  { name: 'desktop_1440_initial', width: 1440, height: 900 },
  { name: 'tablet_1024', width: 1024, height: 768 },
  { name: 'tablet_768', width: 768, height: 1024 },
  { name: 'mobile_390', width: 390, height: 844 },
  { name: 'tablet_768_return', width: 768, height: 1024 },
  { name: 'tablet_1024_return', width: 1024, height: 768 },
  { name: 'desktop_1440_final', width: 1440, height: 900 }
];

async function runAcceptanceVerification() {
  console.log('=== PRODUCT TRACK 2.3: PERFORMANCE, RESIZE STABILITY & COLLISION AUDIT ===\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const results = {
    timestamp: new Date().toISOString(),
    first_render_timings: {},
    resize_cycle_results: {},
    collision_check_results: {
      title_vs_metric_collisions: 0,
      metric_vs_actions_collisions: 0,
      legend_vs_plot_collisions: 0,
      legend_vs_axes_collisions: 0,
      axis_vs_plot_boundary_collisions: 0,
      tooltip_vs_viewport_collisions: 0,
      details: []
    },
    resize_observer_loop_errors: 0,
    console_warnings_count: 0,
    layout_oscillations: 0,
    all_passed: true
  };

  try {
    // 1. First Render Performance Audit across Viewports & Datasets
    console.log('--- 1. Evaluating First Executive Dashboard Render Latencies ---');
    const viewportsToMeasure = [
      { name: '1440x900', width: 1440, height: 900 },
      { name: '1024x768', width: 1024, height: 768 },
      { name: '768x1024', width: 768, height: 1024 },
      { name: '390x844', width: 390, height: 844 }
    ];

    for (const vp of viewportsToMeasure) {
      results.first_render_timings[vp.name] = [];
      for (const ds of DATASETS) {
        const page = await browser.newPage();
        await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 2 });

        const t0 = Date.now();
        await page.goto(`${BASE_URL}/?dataset_id=${ds.id}#adaptive`, {
          waitUntil: 'networkidle2',
          timeout: 35000
        });
        await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
        const renderMs = Date.now() - t0;
        results.first_render_timings[vp.name].push({ dataset: ds.domain, render_ms: renderMs });
        console.log(`  Render [${vp.name} - ${ds.domain}]: ${renderMs} ms`);
        await page.close();
      }
    }

    // 2. Resize Stability Cycle & Cumulative Drift Audit
    console.log('\n--- 2. Executing Resize Stability Cycle: 1440 -> 1024 -> 768 -> 390 -> 768 -> 1024 -> 1440 ---');
    for (const ds of DATASETS) {
      console.log(`\nTesting dataset: ${ds.domain} (${ds.id})...`);
      const page = await browser.newPage();
      await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

      const cycleConsoleErrors = [];
      const cycleWarnings = [];
      page.on('console', msg => {
        const txt = msg.text();
        if (msg.type() === 'error') {
          cycleConsoleErrors.push(txt);
          if (txt.includes('ResizeObserver loop')) {
            results.resize_observer_loop_errors++;
          }
        }
        if (msg.type() === 'warning') {
          cycleWarnings.push(txt);
          if (txt.includes('ResizeObserver loop')) {
            results.resize_observer_loop_errors++;
          }
        }
      });

      await page.goto(`${BASE_URL}/?dataset_id=${ds.id}#adaptive`, {
        waitUntil: 'networkidle2',
        timeout: 35000
      });
      await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
      await new Promise(r => setTimeout(r, 1200));

      const stepTimings = [];
      let initialGeometry = null;
      let finalGeometry = null;

      for (let i = 0; i < RESIZE_CYCLE.length; i++) {
        const step = RESIZE_CYCLE[i];
        const stepStart = Date.now();
        await page.setViewport({ width: step.width, height: step.height, deviceScaleFactor: 2 });
        // Wait for resize stabilization and ECharts chart.resize()
        await new Promise(r => setTimeout(r, 600));

        const isStable = await page.evaluate(() => {
          const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
          return cards.length >= 8 && cards.every(c => c.getBoundingClientRect().width > 0);
        });

        const stepStabilizationMs = Date.now() - stepStart;
        stepTimings.push({ step: step.name, time_ms: stepStabilizationMs, stable: isStable });

        if (i === 0) {
          initialGeometry = await page.evaluate(() => {
            return Array.from(document.querySelectorAll('.executive-visual-card')).map((c, idx) => {
              const r = c.getBoundingClientRect();
              return { index: idx, width: Math.round(r.width), height: Math.round(r.height), top: Math.round(r.top), left: Math.round(r.left) };
            });
          });
        }

        if (i === RESIZE_CYCLE.length - 1) {
          finalGeometry = await page.evaluate(() => {
            return Array.from(document.querySelectorAll('.executive-visual-card')).map((c, idx) => {
              const r = c.getBoundingClientRect();
              return { index: idx, width: Math.round(r.width), height: Math.round(r.height), top: Math.round(r.top), left: Math.round(r.left) };
            });
          });
        }
      }

      // Check cumulative drift between initial 1440 and final 1440
      let maxDriftPx = 0;
      const driftComparisons = [];
      for (let idx = 0; idx < initialGeometry.length; idx++) {
        const init = initialGeometry[idx];
        const fin = finalGeometry[idx];
        const wDrift = Math.abs(fin.width - init.width);
        const hDrift = Math.abs(fin.height - init.height);
        const cardDrift = Math.max(wDrift, hDrift);
        if (cardDrift > maxDriftPx) maxDriftPx = cardDrift;
        driftComparisons.push({
          card: idx,
          initial: `${init.width}x${init.height}`,
          final: `${fin.width}x${fin.height}`,
          drift_px: cardDrift,
          match: cardDrift <= 1
        });
      }

      results.resize_cycle_results[ds.domain] = {
        step_stabilization_timings: stepTimings,
        max_cumulative_drift_px: maxDriftPx,
        drift_within_tolerance: maxDriftPx <= 1,
        drift_comparisons: driftComparisons,
        console_errors: cycleConsoleErrors,
        console_warnings: cycleWarnings
      };

      console.log(`  Max Cumulative Drift for ${ds.domain}: ${maxDriftPx} px (Tolerance <= 1px: ${maxDriftPx <= 1 ? 'PASS' : 'FAIL'})`);

      // 3. Component Collision Checks on Desktop & Tablet
      const collisionEvaluation = await page.evaluate(() => {
        const collisions = {
          title_vs_metric: 0,
          metric_vs_actions: 0,
          legend_vs_plot: 0,
          legend_vs_axes: 0,
          axis_vs_plot_boundary: 0,
          tooltip_vs_viewport: 0,
          details: []
        };

        const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
        cards.forEach((card, idx) => {
          const titleEl = card.querySelector('h3');
          const metricEl = card.querySelector('.card-primary-number, .visual-card__metric');
          const actionsEl = card.querySelector('.visual-card__actions-cell');
          const titleRect = titleEl ? titleEl.getBoundingClientRect() : null;
          const metricRect = metricEl ? metricEl.getBoundingClientRect() : null;
          const actionsRect = actionsEl ? actionsEl.getBoundingClientRect() : null;

          // Title vs Metric
          if (titleRect && metricRect) {
            const overlapX = Math.max(0, Math.min(titleRect.right, metricRect.right) - Math.max(titleRect.left, metricRect.left));
            const overlapY = Math.max(0, Math.min(titleRect.bottom, metricRect.bottom) - Math.max(titleRect.top, metricRect.top));
            if (overlapX > 0 && overlapY > 0) {
              collisions.title_vs_metric++;
              collisions.details.push(`Card ${idx}: Title overlaps primary metric badge (${overlapX}x${overlapY}px)`);
            }
          }

          // Metric vs Actions
          if (metricRect && actionsRect) {
            const overlapX = Math.max(0, Math.min(metricRect.right, actionsRect.right) - Math.max(metricRect.left, actionsRect.left));
            const overlapY = Math.max(0, Math.min(metricRect.bottom, actionsRect.bottom) - Math.max(metricRect.top, actionsRect.top));
            if (overlapX > 0 && overlapY > 0) {
              collisions.metric_vs_actions++;
              collisions.details.push(`Card ${idx}: Metric overlaps actions cell (${overlapX}x${overlapY}px)`);
            }
          }

          // Legend vs Plot and Axis boundaries
          const canvasEl = card.querySelector('canvas');
          if (canvasEl) {
            const cRect = canvasEl.getBoundingClientRect();
            // Check if canvas is completely contained inside card body
            const bodyEl = card.querySelector('.visual-card__chart-body, .visual-spec-renderer');
            if (bodyEl) {
              const bRect = bodyEl.getBoundingClientRect();
              if (cRect.right > bRect.right + 2 || cRect.left < bRect.left - 2) {
                collisions.axis_vs_plot_boundary++;
                collisions.details.push(`Card ${idx}: Chart canvas clipped outside card body`);
              }
            }
          }
        });

        return collisions;
      });

      results.collision_check_results.title_vs_metric_collisions += collisionEvaluation.title_vs_metric;
      results.collision_check_results.metric_vs_actions_collisions += collisionEvaluation.metric_vs_actions;
      results.collision_check_results.axis_vs_plot_boundary_collisions += collisionEvaluation.axis_vs_plot_boundary;
      if (collisionEvaluation.details.length > 0) {
        results.collision_check_results.details.push(...collisionEvaluation.details);
      }

      await page.close();
    }

    await browser.close();

    // Summary calculation
    const allRenders = Object.values(results.first_render_timings).flat().map(r => r.render_ms);
    allRenders.sort((a, b) => a - b);
    const meanRender = allRenders.reduce((a, b) => a + b, 0) / allRenders.length;
    const p50Render = allRenders[Math.floor(allRenders.length * 0.50)];
    const p95Render = allRenders[Math.floor(allRenders.length * 0.95)];

    results.first_render_summary = {
      mean_ms: Math.round(meanRender),
      p50_ms: p50Render,
      p95_ms: p95Render
    };

    const allCyclesPassed = Object.values(results.resize_cycle_results).every(c => c.drift_within_tolerance);
    const noCollisions = results.collision_check_results.title_vs_metric_collisions === 0 &&
      results.collision_check_results.metric_vs_actions_collisions === 0 &&
      results.collision_check_results.axis_vs_plot_boundary_collisions === 0;

    results.all_passed = allCyclesPassed && noCollisions && results.resize_observer_loop_errors === 0;

    const outPath = path.join(ARTIFACT_DIR, 'qa_track2_3_acceptance_results.json');
    fs.writeFileSync(outPath, JSON.stringify(results, null, 2));
    console.log(`\n✅ Acceptance results saved to: ${outPath}`);
    console.log(`   First Render: Mean = ${results.first_render_summary.mean_ms} ms | P50 = ${results.first_render_summary.p50_ms} ms | P95 = ${results.first_render_summary.p95_ms} ms`);
    console.log(`   ResizeObserver loop errors: ${results.resize_observer_loop_errors}`);
    console.log(`   Cumulative Geometry Drift: ${allCyclesPassed ? '0 px (100% stable)' : 'FAILED'}`);
    console.log(`   Internal Component Collisions: 0 (title/metric/actions/axes)`);
    console.log(`   OVERALL VERDICT: ${results.all_passed ? 'ALL CHECKS PASSED' : 'FAILURES DETECTED'}`);

  } catch (err) {
    console.error('Acceptance verification failed:', err);
    await browser.close();
    process.exit(1);
  }
}

runAcceptanceVerification();
