const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const OUTPUT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/rendered_exports/sdr7';
const BASE_URL = 'http://localhost:5175';

if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

async function capture() {
  console.log('=== Starting SDR-7 Rendered Browser Certification ===');
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  // Reset theme to light first
  await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert#explorer`, { waitUntil: 'networkidle0' });
  await page.evaluate(() => {
    localStorage.setItem('highview_theme', 'light');
    document.documentElement.setAttribute('data-theme', 'light');
    window.dispatchEvent(new CustomEvent('highview-theme-change', { detail: { theme: 'light' } }));
  });

  // 1. Desktop Source Mode
  console.log('Capturing: Desktop Source Mode...');
  await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=source#explorer`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('.sdr-source-mode-container table', { timeout: 10000 });
  await new Promise(r => setTimeout(r, 600));
  await page.screenshot({ path: path.join(OUTPUT_DIR, 'sdr7_01_desktop_source_mode.png'), fullPage: false });

  // 2. Desktop Semantics Mode
  console.log('Capturing: Desktop Semantics Mode...');
  await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=semantics#explorer`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('.sdr-semantics-mode-container table tbody tr', { timeout: 10000 });
  await new Promise(r => setTimeout(r, 600));
  await page.screenshot({ path: path.join(OUTPUT_DIR, 'sdr7_02_desktop_semantics_mode.png'), fullPage: false });

  // 3. Desktop Column Detail Drawer
  console.log('Capturing: Desktop Column Detail Drawer...');
  const inspectBtn = await page.$('.sdr-semantics-mode-container table tbody tr button');
  if (inspectBtn) {
    await inspectBtn.click();
    await page.waitForSelector('div[role="dialog"]', { timeout: 5000 });
    await new Promise(r => setTimeout(r, 600));
    await page.screenshot({ path: path.join(OUTPUT_DIR, 'sdr7_03_desktop_column_drawer.png'), fullPage: false });
    await page.keyboard.press('Escape');
    await new Promise(r => setTimeout(r, 400));
  }

  // 4. Desktop Relationships Mode
  console.log('Capturing: Desktop Relationships Mode...');
  await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=relationships#explorer`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('.sdr-relationships-mode-container', { timeout: 10000 });
  await new Promise(r => setTimeout(r, 600));
  await page.screenshot({ path: path.join(OUTPUT_DIR, 'sdr7_04_desktop_relationships_mode.png'), fullPage: false });

  // 5. Desktop Analytical Views Mode
  console.log('Capturing: Desktop Analytical Views Mode...');
  await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=analytical-views#explorer`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('.sdr-analytical-views-mode-container', { timeout: 10000 });
  await new Promise(r => setTimeout(r, 600));
  await page.screenshot({ path: path.join(OUTPUT_DIR, 'sdr7_05_desktop_analytical_views_mode.png'), fullPage: false });

  // 6. Stale Warning Banner (click stale view button)
  console.log('Capturing: Stale View Warning Banner...');
  const viewButtons = await page.$$('.sdr-analytical-views-mode-container button');
  for (const btn of viewButtons) {
    const text = await page.evaluate(el => el.textContent, btn);
    if (text && text.includes('Deprecated Compensation')) {
      await btn.click();
      break;
    }
  }
  await new Promise(r => setTimeout(r, 600));
  await page.screenshot({ path: path.join(OUTPUT_DIR, 'sdr7_06_stale_warning_banner.png'), fullPage: false });

  // 7. Desktop Lineage Drawer
  console.log('Capturing: Desktop Lineage Drawer...');
  const lineageBtn = await page.$('.sdr-analytical-views-mode-container table tbody tr button');
  if (lineageBtn) {
    await lineageBtn.click();
    await page.waitForSelector('div[role="dialog"]', { timeout: 5000 });
    await new Promise(r => setTimeout(r, 600));
    await page.screenshot({ path: path.join(OUTPUT_DIR, 'sdr7_07_desktop_lineage_drawer.png'), fullPage: false });
    await page.keyboard.press('Escape');
    await new Promise(r => setTimeout(r, 400));
  }

  // 8. Mobile Viewport (375x812)
  console.log('Capturing: Mobile Viewport (375x812)...');
  await page.setViewport({ width: 375, height: 812, isMobile: true });
  await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=source#explorer`, { waitUntil: 'networkidle0' });
  await page.waitForSelector('.sdr-source-mode-container table', { timeout: 10000 });
  await new Promise(r => setTimeout(r, 600));
  await page.screenshot({ path: path.join(OUTPUT_DIR, 'sdr7_08_mobile_source_mode.png'), fullPage: false });

  // 9. Dark Theme Semantics
  console.log('Capturing: Dark Theme Semantics...');
  await page.setViewport({ width: 1440, height: 900, isMobile: false });
  await page.goto(`${BASE_URL}/?dataset_id=sdr7_cert&tab=semantics#explorer`, { waitUntil: 'networkidle0' });
  await page.evaluate(() => {
    localStorage.setItem('highview_theme', 'dark');
    document.documentElement.setAttribute('data-theme', 'dark');
    window.dispatchEvent(new CustomEvent('highview-theme-change', { detail: { theme: 'dark' } }));
  });
  await page.waitForSelector('.sdr-semantics-mode-container table tbody tr', { timeout: 10000 });
  await new Promise(r => setTimeout(r, 800));
  await page.screenshot({ path: path.join(OUTPUT_DIR, 'sdr7_09_dark_theme_semantics.png'), fullPage: false });

  // Reset back to light theme
  await page.evaluate(() => {
    localStorage.setItem('highview_theme', 'light');
    document.documentElement.setAttribute('data-theme', 'light');
    window.dispatchEvent(new CustomEvent('highview-theme-change', { detail: { theme: 'light' } }));
  });

  await browser.close();
  console.log(`=== SDR-7 Browser Certification Complete. 9 screenshots saved to: ${OUTPUT_DIR} ===`);
}

capture().catch(err => {
  console.error('Certification capture failed:', err);
  process.exit(1);
});
