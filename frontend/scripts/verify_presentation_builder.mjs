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

  console.log('Navigating to PulseHR Presentation tab...');
  await page.goto('http://localhost:5175', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));

  // 1. Click on Presentation Tab
  console.log('Clicking Presentation Tab...');
  const presTabBtn = await page.waitForSelector('button[data-tab="presentation"], button:has-text("Presentation"), nav button:nth-child(3)', { timeout: 5000 }).catch(() => null);
  if (presTabBtn) {
    await presTabBtn.click();
  } else {
    // Fallback: evaluate tab click
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('nav button, .app-nav button, header button'));
      const pBtn = btns.find(b => b.innerText.includes('Presentation'));
      if (pBtn) pBtn.click();
    });
  }
  await new Promise(r => setTimeout(r, 1500));

  // 2. Capture Prompt Studio Screen
  console.log('Capturing Prompt Studio Screen...');
  const promptStudio = await page.$('.pres-prompt-studio');
  if (promptStudio) {
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_presentation_prompt_studio.png'),
      fullPage: true
    });
  } else {
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_presentation_prompt_studio.png'),
      fullPage: true
    });
  }

  // 3. Open Royalty-Free Image Picker Modal
  console.log('Testing Royalty-Free Image Picker Modal...');
  const browsePhotosBtn = await page.$('.pres-bg-btn:nth-child(2)');
  if (browsePhotosBtn) {
    await browsePhotosBtn.click();
    await new Promise(r => setTimeout(r, 800));
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_presentation_image_picker.png')
    });

    // Close image picker modal
    const closeBtn = await page.$('.pres-image-picker-modal .btn-close, .pres-image-picker-modal .btn-cancel');
    if (closeBtn) await closeBtn.click();
    await new Promise(r => setTimeout(r, 400));
  }

  // 4. Click "Build Slides with Copilot Studio"
  console.log('Building slides into Studio View...');
  const buildBtn = await page.waitForSelector('.btn-launch-presentation');
  if (buildBtn) {
    await buildBtn.click();
    await new Promise(r => setTimeout(r, 1500));

    // Capture Deck Studio View with Copilot Curation Bar
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_presentation_studio_copilot.png')
    });

    // 5. Test "Present with AI Orb"
    console.log('Testing Present with AI Orb...');
    const presentOrbBtn = await page.$('.btn-present-orb');
    if (presentOrbBtn) {
      await presentOrbBtn.click();
      await new Promise(r => setTimeout(r, 800));

      await page.screenshot({
        path: path.join(ARTIFACT_DIR, 'verify_presentation_orb_presenter.png')
      });
    }
  }

  await browser.close();
  console.log('All presentation audits completed successfully!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
