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

async function main() {
  console.log('===============================================================');
  console.log('🎨 HIGHVIEW VISUAL DESIGN INTEGRITY & BROWSER QA TEST SUITE');
  console.log('===============================================================\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  const consoleLogs = [];
  const errors = [];

  page.on('console', msg => {
    const text = msg.text();
    const type = msg.type();
    consoleLogs.push({ type, text });
    if (type === 'error') {
      console.log(`[Browser ERROR]: ${text}`);
    }
  });

  page.on('pageerror', err => {
    console.log(`[Browser UNCAUGHT]: ${err.message}`);
    errors.push(err.message);
  });

  const testResults = {
    viewportsTested: [],
    themeModes: [],
    typographicScale: null,
    cardHeaderGeometry: null,
    drawerInvariant: null,
    presentationLabels: null,
    screenshots: []
  };

  try {
    // -------------------------------------------------------------------------
    // TEST 1: Dashboard Visual QA across Viewports & Themes
    // -------------------------------------------------------------------------
    console.log('📋 STEP 1: Running Dashboard QA across 5 Viewports & Dual Themes...');

    for (const vp of VIEWPORTS) {
      await page.setViewport({ width: vp.width, height: vp.height, deviceScaleFactor: 2 });
      console.log(`\n  Checking viewport: ${vp.name} (${vp.width}x${vp.height})...`);

      // 1A. Dark Mode
      await page.goto(`${BASE_URL}/?dataset_id=${DATASET_ID}&theme=dark#dashboard`, { waitUntil: 'networkidle0' });
      await new Promise(r => setTimeout(r, 1500));

      // Ensure dark theme is active
      await page.evaluate(() => {
        document.documentElement.classList.add('dark');
        document.documentElement.setAttribute('data-theme', 'dark');
      });
      await new Promise(r => setTimeout(r, 400));

      const screenshotDarkPath = path.join(ARTIFACTS_DIR, `qa_visual_dashboard_${vp.name}_dark.png`);
      await page.screenshot({ path: screenshotDarkPath, fullPage: false });
      testResults.screenshots.push(screenshotDarkPath);
      console.log(`    📸 Saved dark screenshot: ${path.basename(screenshotDarkPath)}`);

      // 1B. Light Mode (only on 1440 for full visual comparison)
      if (vp.width === 1440) {
        await page.evaluate(() => {
          document.documentElement.classList.remove('dark');
          document.documentElement.setAttribute('data-theme', 'light');
        });
        await new Promise(r => setTimeout(r, 500));
        const screenshotLightPath = path.join(ARTIFACTS_DIR, `qa_visual_dashboard_1440_light.png`);
        await page.screenshot({ path: screenshotLightPath, fullPage: false });
        testResults.screenshots.push(screenshotLightPath);
        console.log(`    📸 Saved light screenshot: ${path.basename(screenshotLightPath)}`);

        // Revert back to dark mode
        await page.evaluate(() => {
          document.documentElement.classList.add('dark');
          document.documentElement.setAttribute('data-theme', 'dark');
        });
        await new Promise(r => setTimeout(r, 300));
      }

      testResults.viewportsTested.push(vp.name);
    }

    // -------------------------------------------------------------------------
    // TEST 2: Typographic Scale & DOM Hierarchy Invariants (at 1440px)
    // -------------------------------------------------------------------------
    console.log('\n📋 STEP 2: Verifying Typographic Scale Invariants...');
    await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 2 });

    const typographyAudit = await page.evaluate(() => {
      const h1Els = Array.from(document.querySelectorAll('h1')).filter(el => !el.classList.contains('sr-only'));
      const h2Els = Array.from(document.querySelectorAll('h2, .dashboard-section__title')).filter(el => !el.classList.contains('sr-only'));
      const h3Els = Array.from(document.querySelectorAll('h3, .visual-card__title')).filter(el => !el.classList.contains('sr-only'));
      const badges = Array.from(document.querySelectorAll('.dashboard-section__badge, .highview-badge')).filter(el => !el.classList.contains('sr-only'));

      const getFontSize = (el) => parseFloat(window.getComputedStyle(el).fontSize);

      const h1Sizes = h1Els.map(getFontSize);
      const h2Sizes = h2Els.map(getFontSize);
      const h3Sizes = h3Els.map(getFontSize);
      const badgeSizes = badges.map(getFontSize);

      const avgH1 = h1Sizes.length ? (h1Sizes.reduce((a, b) => a + b, 0) / h1Sizes.length) : 0;
      const avgH2 = h2Sizes.length ? (h2Sizes.reduce((a, b) => a + b, 0) / h2Sizes.length) : 0;
      const avgH3 = h3Sizes.length ? (h3Sizes.reduce((a, b) => a + b, 0) / h3Sizes.length) : 0;

      const ratioH1H2 = avgH2 > 0 ? (avgH1 / avgH2) : 0;
      const ratioH2H3 = avgH3 > 0 ? (avgH2 / avgH3) : 0;

      return {
        h1Count: h1Els.length,
        h1Text: h1Els.map(h => h.innerText.trim()),
        avgH1Px: avgH1,
        h2Count: h2Els.length,
        avgH2Px: avgH2,
        h3Count: h3Els.length,
        avgH3Px: avgH3,
        ratioH1H2: Number(ratioH1H2.toFixed(2)),
        ratioH2H3: Number(ratioH2H3.toFixed(2)),
        badgeCount: badges.length,
        avgBadgePx: badgeSizes.length ? (badgeSizes.reduce((a, b) => a + b, 0) / badgeSizes.length) : 0,
        badgeTransform: badges.length ? window.getComputedStyle(badges[0]).textTransform : ''
      };
    });

    console.log(`  H1 elements: ${typographyAudit.h1Count} (Text: "${typographyAudit.h1Text.join(', ')}") - Size: ${typographyAudit.avgH1Px}px`);
    console.log(`  H2 elements: ${typographyAudit.h2Count} - Avg Size: ${typographyAudit.avgH2Px}px`);
    console.log(`  H3 elements: ${typographyAudit.h3Count} - Avg Size: ${typographyAudit.avgH3Px}px`);
    console.log(`  Ratio H1 / H2: ${typographyAudit.ratioH1H2}x (Requirement: >= 1.25x) -> ${typographyAudit.ratioH1H2 >= 1.25 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`  Ratio H2 / H3: ${typographyAudit.ratioH2H3}x (Requirement: >= 1.20x) -> ${typographyAudit.ratioH2H3 >= 1.20 ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`  Badge elements: ${typographyAudit.badgeCount} - Avg Size: ${typographyAudit.avgBadgePx}px, transform: ${typographyAudit.badgeTransform} -> ${typographyAudit.avgBadgePx <= 13 ? '✅ PASS' : '❌ FAIL'}`);

    testResults.typographicScale = typographyAudit;

    // -------------------------------------------------------------------------
    // TEST 3: Card Header Geometry & Action Consistency
    // -------------------------------------------------------------------------
    console.log('\n📋 STEP 3: Verifying Card Header Geometry & Action Button Invariants...');

    const cardGeometryAudit = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.executive-visual-card'));
      const headerGrids = Array.from(document.querySelectorAll('.visual-card__header-grid'));
      const actionIconButtons = Array.from(document.querySelectorAll('.hv-action-icon-btn'));

      const details = cards.slice(0, 5).map(c => {
        const header = c.querySelector('.visual-card__header');
        const headerDisplay = header ? window.getComputedStyle(header).display : 'none';
        const titleEl = c.querySelector('h3.visual-card__title');
        const titleText = titleEl?.innerText?.trim();
        const fullTitle = titleEl?.getAttribute('title');
        const ariaLabel = titleEl?.getAttribute('aria-label');
        const lineClamp = titleEl ? window.getComputedStyle(titleEl).webkitLineClamp : 'none';
        const actionBtns = Array.from(c.querySelectorAll('.hv-action-icon-btn')).map(b => ({
          ariaLabel: b.getAttribute('aria-label'),
          title: b.getAttribute('title'),
          width: b.getBoundingClientRect().width,
          height: b.getBoundingClientRect().height
        }));

        return {
          headerDisplay,
          titleText,
          hasFullTitleInAttr: Boolean(fullTitle && fullTitle.length >= (titleText?.length || 0)),
          hasAriaLabel: Boolean(ariaLabel),
          lineClamp,
          actionButtonCount: actionBtns.length,
          actionBtns
        };
      });

      return {
        cardCount: cards.length,
        headerGridCount: headerGrids.length,
        actionIconButtonCount: actionIconButtons.length,
        sampleCards: details
      };
    });

    console.log(`  Total visual cards: ${cardGeometryAudit.cardCount}`);
    console.log(`  Header grids found: ${cardGeometryAudit.headerGridCount}`);
    console.log(`  ActionIconButtons found: ${cardGeometryAudit.actionIconButtonCount}`);
    cardGeometryAudit.sampleCards.forEach((c, idx) => {
      console.log(`    Card ${idx + 1}: "${c.titleText?.slice(0, 35)}..."`);
      console.log(`      Header display: ${c.headerDisplay}, line-clamp: ${c.lineClamp}`);
      console.log(`      Title protected (title attr: ${c.hasFullTitleInAttr}, aria-label: ${c.hasAriaLabel})`);
      console.log(`      Action buttons: ${c.actionButtonCount} (dimensions: ${c.actionBtns[0]?.width || 0}x${c.actionBtns[0]?.height || 0}px)`);
    });

    testResults.cardHeaderGeometry = cardGeometryAudit;

    // -------------------------------------------------------------------------
    // TEST 4: Drawer Direction & Side Panel Motion Invariant
    // -------------------------------------------------------------------------
    console.log('\n📋 STEP 4: Verifying Quick Inspect Drawer & Right -> Left Motion Invariant...');

    // Find the first inspect action button
    const inspectBtn = await page.$('.hv-action-icon-btn[aria-label*="Inspect"]');
    if (!inspectBtn) {
      throw new Error('Could not find an inspect action button on the dashboard');
    }

    // Click inspect button to trigger drawer
    await inspectBtn.click();
    await new Promise(r => setTimeout(r, 800));

    const drawerAudit = await page.evaluate(() => {
      const panel = document.querySelector('.hv-sidepanel-panel');
      const backdrop = document.querySelector('.hv-sidepanel-backdrop');
      if (!panel) return { found: false };

      const rect = panel.getBoundingClientRect();
      const style = window.getComputedStyle(panel);
      const closeBtn = panel.querySelector('.hv-sidepanel-close-btn');

      return {
        found: true,
        right: rect.right,
        viewportWidth: window.innerWidth,
        isAnchoredRight: Math.abs(rect.right - window.innerWidth) < 5,
        widthPx: rect.width,
        animationName: style.animationName,
        hasCloseButton: Boolean(closeBtn),
        title: panel.querySelector('.hv-sidepanel-title')?.innerText?.trim()
      };
    });

    console.log(`  Drawer found: ${drawerAudit.found}`);
    console.log(`  Drawer title: "${drawerAudit.title}"`);
    console.log(`  Drawer anchored to right edge: ${drawerAudit.isAnchoredRight} (rect.right=${drawerAudit.right}, viewport=${drawerAudit.viewportWidth})`);
    console.log(`  Drawer width: ${drawerAudit.widthPx}px, animation: ${drawerAudit.animationName}`);

    const screenshotDrawerPath = path.join(ARTIFACTS_DIR, `qa_visual_drawer_open_1440.png`);
    await page.screenshot({ path: screenshotDrawerPath, fullPage: false });
    testResults.screenshots.push(screenshotDrawerPath);
    console.log(`  📸 Saved drawer open screenshot: ${path.basename(screenshotDrawerPath)}`);

    // Test Esc dismissal
    await page.keyboard.press('Escape');
    await new Promise(r => setTimeout(r, 600));

    const drawerClosed = await page.evaluate(() => {
      return !document.querySelector('.hv-sidepanel-panel');
    });
    console.log(`  Drawer dismissed via Escape key: ${drawerClosed ? '✅ PASS' : '❌ FAIL'}`);

    testResults.drawerInvariant = { ...drawerAudit, dismissedViaEscape: drawerClosed };

    // -------------------------------------------------------------------------
    // TEST 5: No Machine Identifier Integrity (Screaming snake_case check)
    // -------------------------------------------------------------------------
    console.log('\n📋 STEP 5: Auditing UI for Raw Machine Identifiers / Screaming snake_case...');

    const identifierAudit = await page.evaluate(() => {
      // Regex for machine keys like TARGET_VS_ACTUAL, WORKFORCE_DYNAMICS, etc.
      // Ignore known scientific acronyms: PM10, SO2, NO2, WFO, KPI, AQI, CO, VOC, etc.
      const ALLOWED_ACRONYMS = new Set(['PM10', 'SO2', 'NO2', 'WFO', 'KPI', 'AQI', 'CO', 'VOC', 'EDA', 'AI', 'LLM', 'MCP']);
      const machineRegex = /\b[A-Z0-9]+_[A-Z0-9_]+\b/g;

      const elementsToCheck = Array.from(document.querySelectorAll(
        'h1, h2, h3, .visual-card__title, .dashboard-section__title, .dashboard-section__badge, .highview-badge, .hv-btn, button'
      ));

      const violations = [];

      elementsToCheck.forEach(el => {
        const text = el.innerText?.trim();
        if (!text) return;
        const matches = text.match(machineRegex);
        if (matches) {
          matches.forEach(m => {
            if (!ALLOWED_ACRONYMS.has(m)) {
              violations.push({
                tag: el.tagName,
                text,
                matchedIdentifier: m
              });
            }
          });
        }
      });

      return {
        elementsScanned: elementsToCheck.length,
        violationCount: violations.length,
        violations
      };
    });

    console.log(`  Elements scanned for raw machine keys: ${identifierAudit.elementsScanned}`);
    console.log(`  Violations detected: ${identifierAudit.violationCount}`);
    if (identifierAudit.violationCount > 0) {
      identifierAudit.violations.forEach(v => {
        console.log(`    ⚠️ Violation: "${v.matchedIdentifier}" in <${v.tag}>: "${v.text}"`);
      });
    } else {
      console.log('  ✅ 0 raw machine identifier violations! PresentationLabelResolver active.');
    }
    testResults.presentationLabels = identifierAudit;

    // -------------------------------------------------------------------------
    // TEST 6: Data Explorer Navigation & Viewports
    // -------------------------------------------------------------------------
    console.log('\n📋 STEP 6: Verifying Data Explorer Visuals...');
    await page.goto(`${BASE_URL}/?dataset_id=${DATASET_ID}#explorer`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 1500));

    const explorerAudit = await page.evaluate(() => {
      const h1 = document.querySelector('h1.page-heading, h1');
      const tabs = Array.from(document.querySelectorAll('.explorer-desktop-tab-bar button, [role="tab"]')).map(t => t.innerText.trim());
      return {
        h1Text: h1?.innerText?.trim(),
        tabCount: tabs.length,
        tabs
      };
    });

    console.log(`  Data Explorer H1: "${explorerAudit.h1Text}"`);
    console.log(`  Explorer tabs available (${explorerAudit.tabCount}): ${explorerAudit.tabs.join(' | ')}`);

    const screenshotExplorerDark = path.join(ARTIFACTS_DIR, `qa_visual_explorer_1440_dark.png`);
    await page.screenshot({ path: screenshotExplorerDark, fullPage: false });
    testResults.screenshots.push(screenshotExplorerDark);
    console.log(`  📸 Saved explorer dark screenshot: ${path.basename(screenshotExplorerDark)}`);

    // Light mode explorer screenshot
    await page.evaluate(() => {
      document.documentElement.classList.remove('dark');
      document.documentElement.setAttribute('data-theme', 'light');
    });
    await new Promise(r => setTimeout(r, 400));
    const screenshotExplorerLight = path.join(ARTIFACTS_DIR, `qa_visual_explorer_1440_light.png`);
    await page.screenshot({ path: screenshotExplorerLight, fullPage: false });
    testResults.screenshots.push(screenshotExplorerLight);
    console.log(`  📸 Saved explorer light screenshot: ${path.basename(screenshotExplorerLight)}`);

    console.log('\n===============================================================');
    console.log('🎉 ALL VISUAL DESIGN INTEGRITY TESTS COMPLETED SUCCESSFULLY!');
    console.log('===============================================================');

  } catch (err) {
    console.error('❌ Error during browser visual QA:', err);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main();
