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

  // 1. Desktop fullpage
  console.log('Capturing Desktop full page...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_fullpage_dashboard.png'),
    fullPage: true
  });

  // 2. Capture Priority Insight Card with co-located controls & Store labels
  console.log('Capturing Priority Insight card...');
  const priorityCard = await page.$('.adaptive-priority-card');
  if (priorityCard) {
    await priorityCard.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_priority_card_desktop.png')
    });
  }

  // 3. Capture Forward Outlook Card (check overflow and K, M, B ticks)
  console.log('Capturing Forward Outlook card...');
  const outlookCard = await page.$('[data-testid="forward-outlook-card"], .adaptive-outlook-card');
  if (outlookCard) {
    await outlookCard.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_forward_outlook_desktop.png')
    });
  }

  // 4. Capture Categorical Breakdown Card (check Sales Volume & fleet avg normalization)
  console.log('Capturing Categorical Breakdown card...');
  const breakdownCard = await page.$('.adaptive-breakdown-card');
  if (breakdownCard) {
    await breakdownCard.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_breakdown_card_desktop.png')
    });
  }

  // 5. Test Donut view toggle
  console.log('Testing Donut view...');
  const donutBtn = await page.waitForSelector('.adaptive-priority-chart-wrapper .adaptive-priority-seg-btn:nth-child(2)');
  await donutBtn.click();
  await new Promise(r => setTimeout(r, 800));
  if (priorityCard) {
    await priorityCard.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_priority_donut_desktop.png')
    });
  }

  // 6. Test Table view toggle with scroller
  console.log('Testing Table view...');
  const tableBtn = await page.waitForSelector('.adaptive-priority-chart-wrapper .adaptive-priority-seg-btn:nth-child(3)');
  await tableBtn.click();
  await new Promise(r => setTimeout(r, 800));
  if (priorityCard) {
    await priorityCard.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_priority_table_desktop.png')
    });
  }

  // 7. Test Mobile viewport (390px)
  console.log('Testing Mobile viewport (390px)...');
  await page.setViewport({ width: 390, height: 844 });
  await page.reload({ waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 2000));

  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_mobile_fullpage.png'),
    fullPage: true
  });

  const mobilePriorityCard = await page.$('.adaptive-priority-card');
  if (mobilePriorityCard) {
    await mobilePriorityCard.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_priority_card_mobile.png')
    });
  }

  const mobileOutlookCard = await page.$('[data-testid="forward-outlook-card"], .adaptive-outlook-card');
  if (mobileOutlookCard) {
    await mobileOutlookCard.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_forward_outlook_mobile.png')
    });
  }

  await browser.close();
  console.log('All comprehensive visual audits completed successfully!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
