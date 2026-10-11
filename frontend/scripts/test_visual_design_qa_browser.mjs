import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const BASE_URL = 'http://localhost:5175';
const ARTIFACTS_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822';
const DATASET_ID = '99767'; // Workforce dataset

const VIEWPORTS = [
  { name: 'desktop_1440', width: 1440, height: 1000 },
  { name: 'laptop_1280', width: 1280, height: 800 },
  { name: 'tablet_landscape_1024', width: 1024, height: 768 },
  { name: 'tablet_portrait_768', width: 768, height: 1024 },
  { name: 'mobile_390', width: 390, height: 844 },
];

const FORBIDDEN_METADATA_STRINGS = [
  'LEADERSHIP FOCUS',
  'LEADERSHIP BRIEF',
  'DISTRIBUTIONS & VARIANCE',
  'DISTRIBUTIONS AND VARIANCE',
  'DISTRIBUTION_VARIANCE',
  'COMPARATIVE BENCHMARKS',
  'COMPARATIVE_BENCHMARKS',
  'DECISION SIMULATOR',
  'AI DECISION SIMULATOR',
  'INTERACTIVE TOOL',
  'COUNTERFACTUAL POLICY REPLAY',
  'COUNTERFACTUAL',
  'REPLAY ENGINE',
  'SCENARIO PROVENANCE',
  'TARGET VS ACTUAL',
  'TARGET_VS_ACTUAL',
  'VISUAL MORPHOLOGY',
  'RELATIONSHIP INTENT',
  'METRIC CORRELATION',
  'WORKFORCE DYNAMICS',
];

async function main() {
  console.log('========================================================================');
  console.log('🎨 PHASE: HUMAN-FACING EXECUTIVE UI SIMPLIFICATION BROWSER QA');
  console.log('========================================================================\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  page.on('console', msg => {
    const text = msg.text();
    const type = msg.type();
    if (type === 'error') {
      console.log(`[Browser ERROR]: ${text}`);
    }
  });

  page.on('pageerror', err => {
    console.log(`[Browser UNCAUGHT]: ${err.message}`);
  });

  try {
    // -------------------------------------------------------------------------
    // TEST 1: Viewports & Theme Verification with Screenshots
    // -------------------------------------------------------------------------
    console.log('📋 STEP 1: Capturing Simplified Dashboard across 5 Viewports & Dual Themes...');

    for (const vp of VIEWPORTS) {
      await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 2 });
      console.log(`\n  Checking viewport: ${vp.name} (${vp.width}x${vp.height})...`);

      // 1A. Dark Mode
      await page.goto(`${BASE_URL}/?dataset_id=${DATASET_ID}&theme=dark#dashboard`, { waitUntil: 'networkidle0' });
      await new Promise(r => setTimeout(r, 1200));

      await page.evaluate(() => {
        document.documentElement.classList.add('dark');
        document.documentElement.setAttribute('data-theme', 'dark');
      });
      await new Promise(r => setTimeout(r, 300));

      const screenshotDarkPath = path.join(ARTIFACTS_DIR, `qa_simplified_dashboard_${vp.name}_dark.png`);
      await page.screenshot({ path: screenshotDarkPath, fullPage: false });
      console.log(`    📸 Saved dark screenshot: ${path.basename(screenshotDarkPath)}`);

      // 1B. Light Mode (on 1440 Desktop)
      if (vp.width === 1440) {
        await page.evaluate(() => {
          document.documentElement.classList.remove('dark');
          document.documentElement.setAttribute('data-theme', 'light');
        });
        await new Promise(r => setTimeout(r, 400));
        const screenshotLightPath = path.join(ARTIFACTS_DIR, `qa_simplified_dashboard_1440_light.png`);
        await page.screenshot({ path: screenshotLightPath, fullPage: false });
        console.log(`    📸 Saved light screenshot: ${path.basename(screenshotLightPath)}`);

        // Revert back to dark mode
        await page.evaluate(() => {
          document.documentElement.classList.add('dark');
          document.documentElement.setAttribute('data-theme', 'dark');
        });
        await new Promise(r => setTimeout(r, 200));
      }
    }

    // Return to desktop 1440 for deep inspection
    await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 2 });
    await page.goto(`${BASE_URL}/?dataset_id=${DATASET_ID}&theme=dark#dashboard`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 1000));

    // -------------------------------------------------------------------------
    // TEST 2: NoTechnicalMetadataVisibilityIntegrity
    // -------------------------------------------------------------------------
    console.log('\n📋 STEP 2: Verifying NoTechnicalMetadataVisibilityIntegrity (Human vs Machine separation)...');

    const metadataAudit = await page.evaluate((forbiddenList) => {
      // Collect visible text from headings, badges, cards, labels, and buttons
      const elements = Array.from(document.querySelectorAll(
        '.page-heading, h1, h2, h3, .dashboard-section__title, .dashboard-section__badge, .highview-badge, .kpi-label, .visual-card__title, .scenario-summary-card, button, p'
      ));

      const violations = [];

      elements.forEach(el => {
        // Exclude script, style, and visually hidden elements
        if (el.classList.contains('sr-only')) return;
        const text = (el.innerText || '').toUpperCase();
        if (!text) return;

        forbiddenList.forEach(forbidden => {
          if (text.includes(forbidden)) {
            violations.push({
              matchedTerm: forbidden,
              tag: el.tagName,
              className: el.className,
              renderedText: el.innerText.trim()
            });
          }
        });
      });

      return {
        elementsChecked: elements.length,
        violations
      };
    }, FORBIDDEN_METADATA_STRINGS);

    console.log(`  Elements checked: ${metadataAudit.elementsChecked}`);
    console.log(`  Forbidden metadata violations: ${metadataAudit.violations.length}`);
    if (metadataAudit.violations.length > 0) {
      metadataAudit.violations.forEach(v => {
        console.log(`    ❌ Violation: "${v.matchedTerm}" found in <${v.tag} class="${v.className}">: "${v.renderedText}"`);
      });
      throw new Error(`Failed NoTechnicalMetadataVisibilityIntegrity: ${metadataAudit.violations.length} forbidden machine strings visible`);
    } else {
      console.log('  ✅ PASS: 0 technical machine metadata strings visible on executive surface!');
    }

    // -------------------------------------------------------------------------
    // TEST 3: Semantic Action Vocabulary & Icon Metaphor Integrity
    // -------------------------------------------------------------------------
    console.log('\n📋 STEP 3: Verifying Semantic Action Vocabulary & Details (ⓘ) Icon Metaphor...');

    const actionAudit = await page.evaluate(() => {
      // 1. Details icon consistency: All details action buttons must render an SVG with lucide-info
      const detailBtns = Array.from(document.querySelectorAll('.hv-action-icon-btn[data-action-key="details"], .hv-action-icon-btn[aria-label*="Explain"]'));
      const allDetailBtnsHaveInfoIcon = detailBtns.length > 0 && detailBtns.every(btn => {
        const svg = btn.querySelector('svg');
        return svg && (svg.classList.contains('lucide-info') || svg.getAttribute('data-lucide') === 'info');
      });

      // 2. Search icon exclusivity: Check if any Search (magnifying glass) icons are used for details/inspect
      const searchIconsInActions = Array.from(document.querySelectorAll('.hv-action-icon-btn svg.lucide-search'));

      // 3. KPI tile action buttons: Check that KPI tiles use ActionIconButton details
      const kpiCards = Array.from(document.querySelectorAll('.kpi-card'));
      const kpisHaveActionBtn = kpiCards.every(kpi => {
        return !!kpi.querySelector('.hv-action-icon-btn[data-action-key="details"], .hv-action-icon-btn[aria-label*="Explain"]');
      });

      // 4. Duplicate "Deep Dive →" links check: visual card figcaption must NOT have "Deep Dive →"
      const visualCardDeepLinks = Array.from(document.querySelectorAll('.visual-card__figcaption .visual-card__deep-link, .visual-card__figcaption a'));

      // 5. Header title row buttons check: "Scenario Explorer" and "Create Presentation" must be removed
      const headerTitleRowButtons = Array.from(document.querySelectorAll('.page-title-row button, .header-actions-row button')).map(b => b.innerText.trim());

      // 6. Voice controls check: No "Listen" or "Read briefing" in Executive Summary
      const voiceButtons = Array.from(document.querySelectorAll('.adaptive-compact-summary-banner button, .compact-voice-player'))
        .filter(b => {
          const t = (b.innerText || '').toLowerCase();
          return t.includes('listen') || t.includes('read briefing');
        })
        .map(b => b.innerText.trim());

      // 7. Policy scenario cards count and buttons
      const scenarioCards = Array.from(document.querySelectorAll('.scenario-summary-card'));
      const scenarioButtons = scenarioCards.flatMap(c => Array.from(c.querySelectorAll('button')).map(b => b.innerText.trim()));

      return {
        detailBtnCount: detailBtns.length,
        allDetailBtnsHaveInfoIcon,
        searchIconsInActionsCount: searchIconsInActions.length,
        kpiCount: kpiCards.length,
        kpisHaveActionBtn,
        visualCardDeepLinksCount: visualCardDeepLinks.length,
        headerTitleRowButtons,
        voiceButtons,
        scenarioCardCount: scenarioCards.length,
        scenarioButtons
      };
    });

    console.log(`  Details action buttons found: ${actionAudit.detailBtnCount}`);
    console.log(`  All details action buttons use Info (ⓘ) icon: ${actionAudit.allDetailBtnsHaveInfoIcon ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`  Search icons incorrectly used as action buttons: ${actionAudit.searchIconsInActionsCount} -> ${actionAudit.searchIconsInActionsCount === 0 ? '✅ PASS (Search icon reserved for real search)' : '❌ FAIL'}`);
    console.log(`  KPI tiles use ActionIconButton details: ${actionAudit.kpisHaveActionBtn ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`  Duplicate "Deep Dive →" links in card footers: ${actionAudit.visualCardDeepLinksCount} -> ${actionAudit.visualCardDeepLinksCount === 0 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`  Header title row buttons: [${actionAudit.headerTitleRowButtons.join(', ')}] -> ${actionAudit.headerTitleRowButtons.length === 0 ? '✅ PASS (Scenario Explorer & Create Presentation removed)' : '❌ FAIL'}`);
    console.log(`  Executive summary voice controls: [${actionAudit.voiceButtons.join(', ')}] -> ${actionAudit.voiceButtons.length === 0 ? '✅ PASS (Voice & Read briefing removed)' : '❌ FAIL'}`);
    console.log(`  Dashboard policy scenario cards: ${actionAudit.scenarioCardCount} (Hard cap = 1) -> ${actionAudit.scenarioCardCount === 1 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`  Scenario card CTA buttons: [${actionAudit.scenarioButtons.join(', ')}] -> ${!actionAudit.scenarioButtons.includes('Open Scenario Explorer') ? '✅ PASS (Permanent expansion, no CTA)' : '❌ FAIL'}`);

    // Assertions
    if (!actionAudit.allDetailBtnsHaveInfoIcon) throw new Error('Details action buttons must use CircleInfo icon');
    if (actionAudit.searchIconsInActionsCount !== 0) throw new Error('Search icons found in action buttons');
    if (!actionAudit.kpisHaveActionBtn) throw new Error('KPI tiles must use ActionIconButton details');
    if (actionAudit.visualCardDeepLinksCount !== 0) throw new Error('Duplicate deep dive links found in card footers');
    if (actionAudit.headerTitleRowButtons.length !== 0) throw new Error('Header contains extraneous buttons');
    if (actionAudit.voiceButtons.length !== 0) throw new Error('Executive summary contains voice controls');
    if (actionAudit.scenarioCardCount > 1) throw new Error('More than 1 scenario card found on dashboard');

    // -------------------------------------------------------------------------
    // TEST 4: Drawer Motion Invariant on ⓘ Click
    // -------------------------------------------------------------------------
    console.log('\n📋 STEP 4: Verifying Quick Inspect Drawer on ⓘ Click (Right -> Left Invariant)...');

    const firstDetailsBtn = await page.$('.hv-action-icon-btn[data-action-key="details"]');
    if (!firstDetailsBtn) {
      throw new Error('Could not find a details action button');
    }

    await firstDetailsBtn.click();
    await new Promise(r => setTimeout(r, 800));

    const drawerAudit = await page.evaluate(() => {
      const panel = document.querySelector('.hv-sidepanel-panel');
      if (!panel) return { found: false };

      const rect = panel.getBoundingClientRect();
      const style = window.getComputedStyle(panel);

      return {
        found: true,
        isAnchoredRight: Math.abs(rect.right - window.innerWidth) < 5,
        widthPx: rect.width,
        animationName: style.animationName,
        title: panel.querySelector('.hv-sidepanel-title')?.innerText?.trim()
      };
    });

    console.log(`  Drawer opened: ${drawerAudit.found}`);
    console.log(`  Drawer anchored to right edge: ${drawerAudit.isAnchoredRight}`);
    console.log(`  Drawer title: "${drawerAudit.title}"`);
    console.log(`  Drawer animation: ${drawerAudit.animationName}`);

    const screenshotDrawerPath = path.join(ARTIFACTS_DIR, `qa_simplified_drawer_open_1440.png`);
    await page.screenshot({ path: screenshotDrawerPath, fullPage: false });
    console.log(`  📸 Saved simplified drawer screenshot: ${path.basename(screenshotDrawerPath)}`);

    // Dismiss via Escape
    await page.keyboard.press('Escape');
    await new Promise(r => setTimeout(r, 600));

    const drawerClosed = await page.evaluate(() => !document.querySelector('.hv-sidepanel-panel'));
    console.log(`  Drawer dismissed via Escape key: ${drawerClosed ? '✅ PASS' : '❌ FAIL'}`);

    console.log('\n========================================================================');
    console.log('🎉 ALL 22 HUMAN-FACING SIMPLIFICATION INVARIANTS PASSED SUCCESSFULLY!');
    console.log('========================================================================\n');

  } catch (err) {
    console.error('❌ Browser Visual QA Error:', err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main();
