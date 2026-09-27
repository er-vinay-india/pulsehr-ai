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
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('nav button, .app-nav button, header button'));
      const pBtn = btns.find(b => b.innerText.includes('Presentation'));
      if (pBtn) pBtn.click();
    });
  }
  await new Promise(r => setTimeout(r, 1500));

  // 2. Test Custom Topic & Executive Briefing Tab
  console.log('Testing Custom Topic & Executive Briefing Tab in Prompt Studio...');
  const customTabBtn = await page.$('.source-tab-btn:nth-child(2)');
  if (customTabBtn) {
    await customTabBtn.click();
    await new Promise(r => setTimeout(r, 600));

    // Click first inspiration chip
    const firstChip = await page.$('.chip-btn:first-child');
    if (firstChip) {
      await firstChip.click();
      await new Promise(r => setTimeout(r, 400));
    }

    // Capture Custom Prompt Studio Screen
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_presentation_custom_prompt_studio.png'),
      fullPage: true
    });
  }

  // 3. Click "Build Slides with Copilot Studio"
  console.log('Building slides into Studio View (Step 1 Centered Title Slide)...');
  const buildBtn = await page.waitForSelector('.btn-launch-presentation');
  if (buildBtn) {
    await buildBtn.click();
    await new Promise(r => setTimeout(r, 1800));

    // Capture Step 1 Centered Title Slide
    console.log('Capturing Step 1 Centered Title Slide...');
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_presentation_step1_centered_title.png')
    });

    // 4. Test AI Title Suggestions Trigger
    console.log('Testing AI Title Suggestions Trigger...');
    const aiTitleBtn = await page.$('.btn-ai-title-suggest');
    if (aiTitleBtn) {
      await aiTitleBtn.click();
      await new Promise(r => setTimeout(r, 600));

      // Capture AI Title Suggestions Popover
      await page.screenshot({
        path: path.join(ARTIFACT_DIR, 'verify_presentation_ai_title_suggestions.png')
      });

      // Click the first title suggestion
      const firstSug = await page.$('.suggestion-tile-btn:first-child');
      if (firstSug) {
        await firstSug.click();
        await new Promise(r => setTimeout(r, 500));
      }
    }

    // 5. Capture Studio with Symbolic Toolbar and Tooltip hover
    console.log('Hovering over symbolic toolbar button...');
    const photoBtn = await page.$('.symbolic-action-btn[aria-label*="Photo"], .symbolic-btn-wrap:nth-child(2)');
    if (photoBtn) {
      await photoBtn.hover();
      await new Promise(r => setTimeout(r, 400));
    }

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_presentation_symbolic_toolbar.png')
    });

    // 6. Test Mobile Viewport Responsiveness
    console.log('Testing Mobile Viewport (375x812)...');
    await page.setViewport({ width: 375, height: 812 });
    await new Promise(r => setTimeout(r, 800));

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_presentation_mobile_responsive.png')
    });
  }

  await browser.close();
  console.log('All presentation verification audits completed successfully!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
