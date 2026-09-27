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
  const results = { overflows: {}, studioFound: false };

  console.log('Navigating directly with deck_id to Presentation tab...');
  await page.goto('http://localhost:5175?deck_id=deck_e11c10d71f23', { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 1500));

  // Click on Presentation tab
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('nav button, .app-nav button, header button'));
    const pBtn = btns.find(b => b.innerText.includes('Presentation'));
    if (pBtn) pBtn.click();
  });
  await new Promise(r => setTimeout(r, 1500));

  // Check if studio view is loaded
  const studioFound = await page.evaluate(() => {
    return !!document.querySelector('.pres-studio-body, .presentation-modal-shell.mode-studio');
  });
  console.log('Studio view loaded:', studioFound);
  results.studioFound = studioFound;

  for (const vp of VIEWPORTS) {
    console.log(`Auditing Studio View at ${vp.name} (${vp.width}x${vp.height})...`);
    await page.setViewport({ width: vp.width, height: vp.height });
    await new Promise(r => setTimeout(r, 600));

    const overflowInfo = await page.evaluate((vpWidth) => {
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
        docWidth,
        scrollWidth,
        hasDocOverflow: scrollWidth > vpWidth + 1,
        overflowCount: overflowingElements.length,
        overflowingElements: overflowingElements.slice(0, 5)
      };
    }, vp.width);

    results.overflows[vp.name] = overflowInfo;

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, `pres_${vp.name}_studio_final.png`),
      fullPage: false
    });
  }

  console.log('STUDIO AUDIT RESULTS:', JSON.stringify(results, null, 2));

  await browser.close();
}

run().catch(err => {
  console.error('Studio audit failed:', err);
  process.exit(1);
});
