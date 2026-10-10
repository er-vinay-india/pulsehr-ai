import puppeteer from 'puppeteer';

async function capture() {
  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1100, deviceScaleFactor: 2 });

  // 1. Capture Workforce Dataset 99767
  console.log("Capturing Workforce Dataset 99767...");
  await page.goto('http://localhost:5175/?dataset_id=99767#dashboard', { waitUntil: 'networkidle2' });
  await page.waitForSelector('.supporting-visuals-grid', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 2500));

  const wfPath = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/desktop_workforce_compressed_dashboard_99767.png';
  await page.screenshot({ path: wfPath, fullPage: true });
  console.log(`Saved workforce screenshot to ${wfPath}`);

  // 2. Capture Environmental Dataset 99768
  console.log("Capturing Environmental Dataset 99768...");
  await page.goto('http://localhost:5175/?dataset_id=99768#dashboard', { waitUntil: 'networkidle2' });
  await page.waitForSelector('.supporting-visuals-grid', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 2500));

  const envPath = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/desktop_environmental_compressed_dashboard_99768.png';
  await page.screenshot({ path: envPath, fullPage: true });
  console.log(`Saved environmental screenshot to ${envPath}`);

  await browser.close();
  console.log("Capture complete!");
}

capture().catch(err => {
  console.error("Capture error:", err);
  process.exit(1);
});
