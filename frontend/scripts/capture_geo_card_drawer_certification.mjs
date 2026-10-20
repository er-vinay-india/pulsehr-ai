import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const OUTPUT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/rendered_exports/geographic_intelligence';
fs.mkdirSync(OUTPUT_DIR, { recursive: true });

async function run() {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900'],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

    console.log('Navigating to dashboard with dataset 99795...');
    await page.goto('http://localhost:5175/?dataset_id=99795', { waitUntil: 'networkidle0', timeout: 30000 });

    // Wait for cards and map to render
    await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
    await new Promise((r) => setTimeout(r, 2000));

    // Find the geographic card
    const geoCardSelector = '.executive-visual-card.visual-card--large, .executive-visual-card.visual-card--hero, [data-height-class="tall"]';
    await page.waitForSelector(geoCardSelector, { timeout: 10000 });

    console.log('1. Capturing desktop full dashboard and isolated card (table removed)...');
    await page.screenshot({ path: path.join(OUTPUT_DIR, '01_desktop_geo_dashboard_no_table.png'), fullPage: true });

    const geoCard = await page.$(geoCardSelector);
    if (geoCard) {
      await geoCard.screenshot({ path: path.join(OUTPUT_DIR, '01_isolated_geo_map_card.png') });
    }

    console.log('2. Clicking "View ranking →" to test lightweight Drawer...');
    const viewRankingBtn = await page.$('.geo-view-ranking-btn');
    if (viewRankingBtn) {
      await viewRankingBtn.click();
      await page.waitForSelector('.drawer-panel .datatable-wrapper', { timeout: 8000 });
      await new Promise((r) => setTimeout(r, 800));

      await page.screenshot({ path: path.join(OUTPUT_DIR, '02_geo_ranking_drawer_open.png') });
      console.log('Drawer screenshot captured.');

      // Press Escape to dismiss drawer
      await page.keyboard.press('Escape');
      await new Promise((r) => setTimeout(r, 600));
    } else {
      console.warn('View ranking button not found!');
    }

    console.log('3. Switching metric to "Population 2011"...');
    const metricButtons = await page.$$('.geo-metric-selector button');
    for (const btn of metricButtons) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text.includes('Population 2011')) {
        await btn.click();
        await new Promise((r) => setTimeout(r, 1200));
        break;
      }
    }

    if (geoCard) {
      await geoCard.screenshot({ path: path.join(OUTPUT_DIR, '03_metric_switch_population_bubbles.png') });
    }

    console.log('4. Switching metric to "Decadal Population Growth Rate"...');
    for (const btn of metricButtons) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text.includes('Growth')) {
        await btn.click();
        await new Promise((r) => setTimeout(r, 1200));
        break;
      }
    }

    if (geoCard) {
      await geoCard.screenshot({ path: path.join(OUTPUT_DIR, '04_metric_switch_growth_choropleth.png') });
    }

    console.log('5. Toggling Dark Mode...');
    // Find dark mode toggle button
    const darkToggle = await page.$('[aria-label*="dark"], [aria-label*="theme"], .theme-toggle, button[title*="Dark"], button[title*="Theme"]');
    if (darkToggle) {
      await darkToggle.click();
      await new Promise((r) => setTimeout(r, 1000));
      if (geoCard) {
        await geoCard.screenshot({ path: path.join(OUTPUT_DIR, '05_dark_mode_geo_map.png') });
      }
      // Revert dark mode
      await darkToggle.click();
      await new Promise((r) => setTimeout(r, 600));
    } else {
      // Direct class toggle if button not clicked
      await page.evaluate(() => document.documentElement.classList.toggle('dark'));
      await new Promise((r) => setTimeout(r, 600));
      if (geoCard) {
        await geoCard.screenshot({ path: path.join(OUTPUT_DIR, '05_dark_mode_geo_map.png') });
      }
      await page.evaluate(() => document.documentElement.classList.remove('dark'));
    }

    console.log('6. Capturing Mobile Viewport (375x812)...');
    await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 2 });
    await new Promise((r) => setTimeout(r, 1000));
    const mobileGeoCard = await page.$(geoCardSelector);
    if (mobileGeoCard) {
      await mobileGeoCard.screenshot({ path: path.join(OUTPUT_DIR, '06_mobile_geo_card.png') });
    }

    console.log('All certification captures successfully saved to:', OUTPUT_DIR);
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error('Puppeteer capture failed:', err);
  process.exit(1);
});
