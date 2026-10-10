import puppeteer from 'puppeteer';
import { fileURLToPath } from 'url';
import path from 'path';

async function capture() {
  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1100, deviceScaleFactor: 2 });

  const activeDatasetId = 99762;
  const targetUrl = `http://localhost:5175/?dataset_id=${activeDatasetId}#adaptive`;
  console.log(`Navigating to ${targetUrl}...`);

  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log('BROWSER ERROR:', msg.text());
    }
  });

  await page.goto(targetUrl, { waitUntil: 'networkidle2' });

  // Wait for insights grid to render
  console.log("Waiting for executive dashboard cards...");
  try {
    await page.waitForSelector('.unified-dataset-insights-section, .unified-executive-insights-grid, [data-testid="hero-visual-wrapper"]', { timeout: 10000 });
  } catch (e) {
    console.log("Selector wait timeout, continuing...");
  }

  // Wait 3s for ECharts animations
  await new Promise(r => setTimeout(r, 3000));

  const outPath = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/desktop_executive_dashboard_environmental_99762.png';
  await page.screenshot({ path: outPath, fullPage: false });
  console.log(`Saved viewport screenshot to ${outPath}`);

  const fullPath = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/desktop_executive_dashboard_environmental_full_99762.png';
  await page.screenshot({ path: fullPath, fullPage: true });
  console.log(`Saved full page screenshot to ${fullPath}`);

  await browser.close();
}

capture().catch(err => {
  console.error("Screenshot error:", err);
  process.exit(1);
});
