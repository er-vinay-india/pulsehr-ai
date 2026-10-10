/**
 * Script to capture high-res screenshots of the Phase 10 Executive Scenario Explorer.
 */
import puppeteer from 'puppeteer-core';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const artifactDir = '/Users/vinayksharma/.gemini/antigravity-ide/brain/9cd70832-7bbd-449d-b18c-68954cd00123';

async function capture() {
  const browser = await puppeteer.launch({
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    defaultViewport: null,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1200, deviceScaleFactor: 2 });

  console.log("Navigating to executive dashboard...");
  await page.goto('http://localhost:5175/?dataset_id=99747#adaptive', { waitUntil: 'networkidle2' });
  await page.waitForSelector('.unified-dataset-insights-section', { timeout: 15000 });

  // Click on "Scenario Explorer" button in header-actions-row
  console.log("Opening Scenario Explorer...");
  const buttons = await page.$$('.header-actions-row button');
  for (const b of buttons) {
    const text = await page.evaluate(el => el.innerText, b);
    if (text.includes("Scenario Explorer")) {
      await b.click();
      break;
    }
  }

  // Wait for scenario explorer to render
  const explorerEl = await page.waitForSelector('.executive-scenario-explorer', { timeout: 10000 });
  await page.evaluate(el => el.scrollIntoView({ behavior: 'instant', block: 'start' }), explorerEl);
  await new Promise(r => setTimeout(r, 2000));

  // Light Mode Element Screenshot
  const lightPath = path.join(artifactDir, 'executive_scenario_explorer_light.png');
  await explorerEl.screenshot({ path: lightPath });
  console.log("✅ Saved Light Mode Element Screenshot:", lightPath);

  // Switch to Dark Mode on a fresh page with dark theme initialized
  const darkPage = await browser.newPage();
  await darkPage.setViewport({ width: 1440, height: 1200, deviceScaleFactor: 2 });
  await darkPage.evaluateOnNewDocument(() => {
    localStorage.setItem('highview_theme', 'dark');
  });

  console.log("Navigating to executive dashboard (Dark Mode)...");
  await darkPage.goto('http://localhost:5175/?dataset_id=99747#adaptive', { waitUntil: 'networkidle2' });
  await darkPage.waitForSelector('.unified-dataset-insights-section', { timeout: 15000 });

  const darkButtons = await darkPage.$$('.header-actions-row button');
  for (const b of darkButtons) {
    const text = await darkPage.evaluate(el => el.innerText, b);
    if (text.includes("Scenario Explorer")) {
      await b.click();
      break;
    }
  }

  const darkExplorerEl = await darkPage.waitForSelector('.executive-scenario-explorer', { timeout: 10000 });
  await darkPage.evaluate(el => el.scrollIntoView({ behavior: 'instant', block: 'start' }), darkExplorerEl);
  await new Promise(r => setTimeout(r, 2000));

  const darkPath = path.join(artifactDir, 'executive_scenario_explorer_dark.png');
  await darkExplorerEl.screenshot({ path: darkPath });
  console.log("✅ Saved Dark Mode Element Screenshot:", darkPath);

  await browser.close();
}

capture().catch(err => {
  console.error("Error capturing scenario explorer screenshots:", err);
  process.exit(1);
});
