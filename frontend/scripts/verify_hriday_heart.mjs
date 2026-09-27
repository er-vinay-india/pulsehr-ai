import puppeteer from 'puppeteer';
import path from 'path';

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/98708ce3-6bc0-44d2-8c5c-f7a790e87154';

async function run() {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--autoplay-policy=no-user-gesture-required']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 950 });

  console.log('Navigating to PulseHR...');
  await page.goto('http://localhost:5175', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));

  // 1. Capture Floating HRIDAY Launcher in bottom-right
  console.log('Capturing HRIDAY Floating Launcher...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_hriday_launcher_docked.png')
  });

  // 2. Open HRIDAY Drawer
  console.log('Clicking HRIDAY Launcher...');
  const launcher = await page.waitForSelector('.hriday-global-launcher, .global-copilot-launcher', { timeout: 5000 });
  if (launcher) {
    await launcher.click();
    await new Promise(r => setTimeout(r, 1200));

    console.log('Capturing Open HRIDAY Drawer...');
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_hriday_drawer_open.png')
    });

    // Close the drawer before moving to presentation
    const closeBtn = await page.$('.copilot-header-actions .close');
    if (closeBtn) {
      await closeBtn.click();
      await new Promise(r => setTimeout(r, 600));
    }
  }

  // 3. Navigate to Presentation tab
  console.log('Navigating to Presentation tab...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('nav button, .app-nav button, header button'));
    const pBtn = btns.find(b => b.innerText.includes('Presentation'));
    if (pBtn) pBtn.click();
  });
  await new Promise(r => setTimeout(r, 2000));

  // Launch Studio View if on prompt screen
  console.log('Building slides to enter Studio View...');
  const launchBtn = await page.waitForSelector('.btn-launch-presentation', { timeout: 6000 }).catch(() => null);
  if (launchBtn) {
    await launchBtn.click();
    await new Promise(r => setTimeout(r, 2500));
  }

  // Click HRIDAY AI Heart / Presenter button in Studio View (.btn-present-orb)
  console.log('Clicking HRIDAY AI Heart Presenter button in Studio...');
  const heartBtn = await page.waitForSelector('.btn-present-orb', { timeout: 6000 });
  if (heartBtn) {
    await heartBtn.click();
    await page.waitForSelector('.acoustic-orb-presenter', { timeout: 6000 });
    await new Promise(r => setTimeout(r, 1200));
  }

  console.log('Capturing HRIDAY Anatomical Red Heart Presenter Modal...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_hriday_anatomical_heart_presenter.png')
  });

  // Expand the HRIDAY Heart HUD card
  console.log('Expanding HRIDAY Heart HUD card...');
  const triggerBtn = await page.$('.hriday-heart-trigger');
  if (triggerBtn) {
    await triggerBtn.click();
    await new Promise(r => setTimeout(r, 1000));
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_hriday_expanded_heart_stage.png')
    });
  }

  await browser.close();
  console.log('HRIDAY Heart & Voice verification completed successfully!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
