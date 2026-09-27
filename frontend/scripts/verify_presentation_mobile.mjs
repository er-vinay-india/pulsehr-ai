import puppeteer from 'puppeteer';
import path from 'path';

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/98708ce3-6bc0-44d2-8c5c-f7a790e87154';

const VIEWPORTS = [
  { name: 'mobile_320', width: 320, height: 667 },
  { name: 'mobile_375', width: 375, height: 667 },
  { name: 'mobile_390', width: 390, height: 844 },
  { name: 'tablet_768', width: 768, height: 1024 },
  { name: 'desktop_1280', width: 1280, height: 800 },
];

async function run() {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  const results = {
    overflows: {},
    tapTargets: {},
    consoleErrors: []
  };

  page.on('console', msg => {
    if (msg.type() === 'error') {
      results.consoleErrors.push(msg.text());
    }
  });

  page.on('pageerror', err => {
    results.consoleErrors.push(err.toString());
  });

  console.log('Navigating to http://localhost:5175...');
  await page.goto('http://localhost:5175', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1500));

  // Switch to Presentation tab
  console.log('Switching to Presentation tab...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('nav button, .app-nav button, header button'));
    const pBtn = btns.find(b => b.innerText.includes('Presentation'));
    if (pBtn) pBtn.click();
  });
  await new Promise(r => setTimeout(r, 1500));

  // Loop over viewports to inspect Prompt Studio
  for (const vp of VIEWPORTS) {
    console.log(`Checking Prompt Studio at ${vp.name} (${vp.width}x${vp.height})...`);
    await page.setViewport({ width: vp.width, height: vp.height });
    await new Promise(r => setTimeout(r, 600));

    // Check for horizontal overflow
    const overflowInfo = await page.evaluate((vpWidth) => {
      const docWidth = document.documentElement.clientWidth;
      const scrollWidth = document.documentElement.scrollWidth;
      const bodyScrollWidth = document.body.scrollWidth;
      
      const overflowingElements = [];
      const allEls = document.querySelectorAll('*');
      for (const el of allEls) {
        const rect = el.getBoundingClientRect();
        if (rect.right > vpWidth + 1.5) { // allow 1.5px subpixel tolerance
          // Ignore fixed position offscreen or modals not currently open
          const style = window.getComputedStyle(el);
          if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
            overflowingElements.push({
              tag: el.tagName,
              className: el.className ? String(el.className).slice(0, 50) : '',
              right: Math.round(rect.right),
              width: Math.round(rect.width),
              vpWidth
            });
          }
        }
      }
      return {
        docWidth,
        scrollWidth,
        bodyScrollWidth,
        hasDocOverflow: scrollWidth > vpWidth + 1,
        overflowingElements: overflowingElements.slice(0, 10)
      };
    }, vp.width);

    results.overflows[vp.name] = overflowInfo;

    // Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, `pres_${vp.name}_prompt_studio.png`),
      fullPage: false
    });
  }

  // Open Image Picker Modal at 375px and test responsiveness
  console.log('Testing Image Picker Modal at 375px...');
  await page.setViewport({ width: 375, height: 667 });
  await page.evaluate(() => {
    const imgRadio = document.querySelectorAll('.pres-bg-card')[1];
    if (imgRadio) imgRadio.click();
  });
  await new Promise(r => setTimeout(r, 800));

  const modalOverflow = await page.evaluate((vpWidth) => {
    const modalShell = document.querySelector('.pres-image-picker-modal');
    if (!modalShell) return { found: false };
    const rect = modalShell.getBoundingClientRect();
    return {
      found: true,
      rect: { left: rect.left, right: rect.right, width: rect.width },
      fitsViewport: rect.right <= vpWidth + 1 && rect.left >= -1
    };
  }, 375);

  results.modalOverflow = modalOverflow;

  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'pres_mobile_375_image_modal.png'),
    fullPage: false
  });

  // Close Image Picker Modal
  await page.evaluate(() => {
    const closeBtn = document.querySelector('.pres-image-picker-modal .btn-close, .pres-image-picker-modal .btn-cancel');
    if (closeBtn) closeBtn.click();
  });
  await new Promise(r => setTimeout(r, 600));

  // Generate a Deck to test DeckGeneratingView and DeckStudioView
  console.log('Launching deck generation...');
  await page.evaluate(() => {
    const launchBtn = document.querySelector('.btn-launch-presentation');
    if (launchBtn) launchBtn.click();
  });

  // Capture generating view at 390px
  await page.setViewport({ width: 390, height: 844 });
  await new Promise(r => setTimeout(r, 1200));

  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'pres_mobile_390_generating_view.png'),
    fullPage: false
  });

  // Wait for studio view or complete generation (max 35s)
  console.log('Waiting for deck studio view...');
  let studioLoaded = false;
  for (let i = 0; i < 35; i++) {
    await new Promise(r => setTimeout(r, 1000));
    studioLoaded = await page.evaluate(() => {
      return !!document.querySelector('.pres-studio-body, .presentation-deck-studio, .deck-studio-root, .pres-stage-container');
    });
    if (studioLoaded) {
      console.log(`Deck studio loaded at second ${i + 1}!`);
      break;
    }
  }

  if (studioLoaded) {
    console.log('Studio loaded! Testing Studio across viewports...');
    for (const vp of VIEWPORTS) {
      await page.setViewport({ width: vp.width, height: vp.height });
      await new Promise(r => setTimeout(r, 600));

      const studioOverflow = await page.evaluate((vpWidth) => {
        const docWidth = document.documentElement.clientWidth;
        const scrollWidth = document.documentElement.scrollWidth;
        const overflowingElements = [];
        const allEls = document.querySelectorAll('*');
        for (const el of allEls) {
          const rect = el.getBoundingClientRect();
          if (rect.right > vpWidth + 1.5) {
            const style = window.getComputedStyle(el);
            if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
              overflowingElements.push({
                tag: el.tagName,
                className: el.className ? String(el.className).slice(0, 50) : '',
                right: Math.round(rect.right),
                width: Math.round(rect.width)
              });
            }
          }
        }
        return {
          scrollWidth,
          hasDocOverflow: scrollWidth > vpWidth + 1,
          overflowCount: overflowingElements.length,
          overflowingElements: overflowingElements.slice(0, 5)
        };
      }, vp.width);

      results[`studio_${vp.name}`] = studioOverflow;

      await page.screenshot({
        path: path.join(ARTIFACT_DIR, `pres_${vp.name}_studio_view.png`),
        fullPage: false
      });
    }
  } else {
    console.log('Studio view did not finish in time or failed.');
  }

  console.log('RESULTS:', JSON.stringify(results, null, 2));

  await browser.close();
}

run().catch(err => {
  console.error('Test run failed:', err);
  process.exit(1);
});
