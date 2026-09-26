import puppeteer from 'puppeteer';
import path from 'path';

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/98708ce3-6bc0-44d2-8c5c-f7a790e87154';

async function run() {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  console.log('Navigating to http://localhost:5175...');
  await page.goto('http://localhost:5175', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));

  // 1. Full-page capture of current Dashboard
  console.log('Capturing full dashboard...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'dashboard_audit_fullpage.png'),
    fullPage: true
  });

  // 2. Capture viewport of top area (Scope Bar, KPIs, Priority Insight)
  console.log('Capturing top area...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'dashboard_audit_top_viewport.png'),
    fullPage: false
  });

  // 3. Scroll down to capture charts and sections
  console.log('Capturing mid section...');
  await page.evaluate(() => window.scrollBy(0, 800));
  await new Promise(r => setTimeout(r, 800));
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'dashboard_audit_mid_viewport.png'),
    fullPage: false
  });

  // 4. Scroll to bottom sections
  console.log('Capturing bottom section...');
  await page.evaluate(() => window.scrollBy(0, 1000));
  await new Promise(r => setTimeout(r, 800));
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'dashboard_audit_bottom_viewport.png'),
    fullPage: false
  });

  await browser.close();
  console.log('Dashboard audit capture completed!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
