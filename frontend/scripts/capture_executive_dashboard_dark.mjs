import puppeteer from 'puppeteer';

async function captureDark() {
  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1100, deviceScaleFactor: 2 });

  await page.evaluateOnNewDocument(() => {
    localStorage.setItem("highview_theme", "dark");
  });

  console.log("Navigating to http://localhost:5175/?dataset_id=99747#adaptive in Dark Theme...");
  await page.goto('http://localhost:5175/?dataset_id=99747#adaptive', { waitUntil: 'networkidle2' });

  await page.waitForSelector('.unified-dataset-insights-section', { timeout: 15000 });
  await page.waitForSelector('.hero-chart-container', { timeout: 15000 });

  await new Promise(r => setTimeout(r, 2000));

  const darkPath = '/Users/vinayksharma/.gemini/antigravity-ide/brain/9cd70832-7bbd-449d-b18c-68954cd00123/executive_dashboard_dark_presentation.png';
  await page.screenshot({ path: darkPath, fullPage: true });
  console.log(`Saved dark full page screenshot to ${darkPath}`);

  await browser.close();
}

captureDark().catch(err => {
  console.error("Screenshot error:", err);
  process.exit(1);
});
