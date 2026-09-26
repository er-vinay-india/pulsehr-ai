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
  await page.setViewport({ width: 1440, height: 1000 });

  console.log('Navigating to http://localhost:5175...');
  await page.goto('http://localhost:5175', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2500));

  // 1. Exception Watch Card Desktop
  console.log('Capturing Exception Watch card desktop...');
  const exceptionCard = await page.$('.adaptive-exception-card');
  if (exceptionCard) {
    await exceptionCard.scrollIntoView();
    await new Promise(r => setTimeout(r, 500));
    await exceptionCard.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_exception_watch_desktop.png')
    });
    console.log('Saved verify_exception_watch_desktop.png');

    // Toggle data table
    console.log('Toggling accessible table...');
    const tableBtn = await page.$('.btn-toggle-table');
    if (tableBtn) {
      await tableBtn.click();
      await new Promise(r => setTimeout(r, 600));
      await exceptionCard.screenshot({
        path: path.join(ARTIFACT_DIR, 'verify_exception_watch_table_desktop.png')
      });
      console.log('Saved verify_exception_watch_table_desktop.png');
      // Toggle back to chart
      await tableBtn.click();
      await new Promise(r => setTimeout(r, 400));
    }
  } else {
    console.error('Exception card not found!');
  }

  // 2. Exception Watch Mobile (390px)
  console.log('Capturing Exception Watch card mobile (390px)...');
  await page.setViewport({ width: 390, height: 844, isMobile: true });
  await new Promise(r => setTimeout(r, 800));
  const exceptionCardMobile = await page.$('.adaptive-exception-card');
  if (exceptionCardMobile) {
    await exceptionCardMobile.scrollIntoView();
    await new Promise(r => setTimeout(r, 500));
    await exceptionCardMobile.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_exception_watch_mobile.png')
    });
    console.log('Saved verify_exception_watch_mobile.png');
  }

  await browser.close();
  console.log('Done!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
