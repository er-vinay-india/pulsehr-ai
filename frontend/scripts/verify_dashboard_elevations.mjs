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
  await page.setViewport({ width: 1440, height: 950 });

  console.log('Navigating to http://localhost:5175...');
  await page.goto('http://localhost:5175', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));

  // 1. Capture Top Executive Viewport with Top 10 Bounded Bar & Formatted Values
  console.log('Capturing Top Executive Viewport...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_dashboard_top10_bounded.png'),
    fullPage: false
  });

  // 2. Test Donut view toggle
  console.log('Testing Donut View...');
  const donutBtn = await page.waitForSelector('.adaptive-priority-seg-btn:nth-child(2)');
  await donutBtn.click();
  await new Promise(r => setTimeout(r, 800));
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_dashboard_donut_view.png'),
    fullPage: false
  });

  // 3. Test Table view toggle
  console.log('Testing Table View...');
  const tableBtn = await page.waitForSelector('.adaptive-priority-seg-btn:nth-child(3)');
  await tableBtn.click();
  await new Promise(r => setTimeout(r, 800));
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_dashboard_table_view.png'),
    fullPage: false
  });

  // 4. Switch back to Bar and test Extremes density pill
  console.log('Testing Bar Extremes Density Pill...');
  const barBtn = await page.waitForSelector('.adaptive-priority-seg-btn:nth-child(1)');
  await barBtn.click();
  await new Promise(r => setTimeout(r, 500));
  const extremesBtn = await page.$('.density-pill-btn:nth-child(2)');
  if (extremesBtn) {
    await extremesBtn.click();
    await new Promise(r => setTimeout(r, 800));
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_dashboard_extremes_pill.png'),
      fullPage: false
    });
  }

  // 5. Test Priority Insight Inspection modal
  console.log('Testing Analysis Details & Inspection modal...');
  const detailsBtn = await page.$('.adaptive-priority-btn:last-child');
  if (detailsBtn) {
    await detailsBtn.click();
    await new Promise(r => setTimeout(r, 600));
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_dashboard_analysis_drawer.png'),
      fullPage: false
    });
  }

  await browser.close();
  console.log('Dashboard verification successfully completed!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
