import puppeteer from 'puppeteer';

async function capture() {
  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1100, deviceScaleFactor: 2 });

  let activeDatasetId = 99750;
  try {
    const dsRes = await fetch('http://localhost:5175/api/upload/datasets');
    if (dsRes.ok) {
      const dsList = await dsRes.json();
      if (dsList && dsList.length > 0) activeDatasetId = dsList[0].id;
    }
  } catch (e) {}

  console.log(`Navigating to http://localhost:5175/?dataset_id=${activeDatasetId}#adaptive ...`);
  await page.goto(`http://localhost:5175/?dataset_id=${activeDatasetId}#adaptive`, { waitUntil: 'networkidle2' });

  // Wait for the insights section to render
  console.log("Waiting for executive dashboard cards...");
  await page.waitForSelector('.unified-dataset-insights-section', { timeout: 15000 });
  await page.waitForSelector('.hero-chart-container', { timeout: 15000 });

  // Wait 2s for ECharts animations to complete
  await new Promise(r => setTimeout(r, 2000));

  const outPath = '/Users/vinayksharma/.gemini/antigravity-ide/brain/9cd70832-7bbd-449d-b18c-68954cd00123/executive_dashboard_presentation_corrected.png';
  await page.screenshot({ path: outPath, fullPage: false });
  console.log(`Saved screenshot to ${outPath}`);

  // Also capture the full page
  const fullPagePath = '/Users/vinayksharma/.gemini/antigravity-ide/brain/9cd70832-7bbd-449d-b18c-68954cd00123/executive_dashboard_full_presentation.png';
  await page.screenshot({ path: fullPagePath, fullPage: true });
  console.log(`Saved full page screenshot to ${fullPagePath}`);

  await browser.close();
}

capture().catch(err => {
  console.error("Screenshot error:", err);
  process.exit(1);
});
