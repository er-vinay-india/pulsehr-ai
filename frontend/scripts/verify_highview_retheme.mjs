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

  console.log('1. Navigating to Dashboard...');
  await page.goto('http://localhost:5175', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));

  // Screenshot 1: Dashboard Top
  console.log('Capturing Dashboard...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_retheme_dashboard.png')
  });

  // Screenshot 2: Dashboard Footer
  console.log('Capturing Footer...');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_retheme_dashboard_footer.png')
  });

  // Screenshot 3: Open HRIDAY drawer
  console.log('Opening HRIDAY copilot launcher...');
  await page.evaluate(() => window.scrollTo(0, 0));
  const launcher = await page.$('.global-copilot-launcher');
  if (launcher) {
    await launcher.click();
    await new Promise(r => setTimeout(r, 1000));
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_retheme_hriday_drawer.png')
    });
    // Close drawer
    const closeBtn = await page.$('.copilot-drawer-header .btn-icon-close, .copilot-drawer-header button');
    if (closeBtn) {
      await closeBtn.click();
      await new Promise(r => setTimeout(r, 600));
    }
  }

  // Screenshot 4: Explore Tab
  console.log('Switching to Explore Tab...');
  const exploreTab = await page.evaluateHandle(() => {
    const tabs = Array.from(document.querySelectorAll('.tabs-nav-segmented button, .tabs-nav-segmented .nav-segment'));
    return tabs.find(t => t.textContent.toLowerCase().includes('explore'));
  });
  if (exploreTab) {
    await exploreTab.click();
    await new Promise(r => setTimeout(r, 1500));
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_retheme_explorer.png')
    });
  }

  // Screenshot 5: Presentation Tab
  console.log('Switching to Presentations Tab...');
  const presTab = await page.evaluateHandle(() => {
    const tabs = Array.from(document.querySelectorAll('.tabs-nav-segmented button, .tabs-nav-segmented .nav-segment'));
    return tabs.find(t => t.textContent.toLowerCase().includes('presentation'));
  });
  if (presTab) {
    await presTab.click();
    await new Promise(r => setTimeout(r, 1500));
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_retheme_presentation.png')
    });
  }

  // Screenshot 6: Mobile (390px)
  console.log('Testing Mobile View (390x844)...');
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
  // Go back to Dashboard
  const dashTab = await page.evaluateHandle(() => {
    const tabs = Array.from(document.querySelectorAll('.tabs-nav-segmented button, .tabs-nav-segmented .nav-segment'));
    return tabs.find(t => t.textContent.toLowerCase().includes('dashboard'));
  });
  if (dashTab) {
    await dashTab.click();
    await new Promise(r => setTimeout(r, 1000));
  }
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_retheme_mobile.png')
  });

  await browser.close();
  console.log('All verification screenshots captured successfully!');
}

run().catch(err => {
  console.error('Error during verification:', err);
  process.exit(1);
});
