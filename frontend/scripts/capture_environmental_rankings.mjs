import puppeteer from 'puppeteer';

async function capture() {
  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1100, deviceScaleFactor: 2 });

  const activeDatasetId = 99762;
  const targetUrl = `http://localhost:5175/?dataset_id=${activeDatasetId}#explorer?tab=rankings`;
  console.log(`Navigating to ${targetUrl}...`);

  await page.goto(targetUrl, { waitUntil: 'networkidle2' });

  // Wait 3s for rankings component and charts to render
  await new Promise(r => setTimeout(r, 3000));

  const outPath = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/desktop_explorer_rankings_environmental_99762.png';
  await page.screenshot({ path: outPath, fullPage: false });
  console.log(`Saved rankings screenshot to ${outPath}`);

  await browser.close();
}

capture().catch(err => {
  console.error("Screenshot error:", err);
  process.exit(1);
});
