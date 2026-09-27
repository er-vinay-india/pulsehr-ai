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

  const consoleLogs = [];
  page.on('console', msg => {
    consoleLogs.push({ type: msg.type(), text: msg.text() });
  });

  const pageErrors = [];
  page.on('pageerror', err => {
    pageErrors.push(err.toString());
  });

  console.log('Navigating to http://localhost:5175...');
  await page.goto('http://localhost:5175', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));

  // Click on Presentation tab
  console.log('Switching to Presentation tab...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('nav button, .app-nav button, header button'));
    const pBtn = btns.find(b => b.innerText.includes('Presentation'));
    if (pBtn) pBtn.click();
  });
  await new Promise(r => setTimeout(r, 1500));

  // Screenshot Light Mode - Dashboard Truth
  console.log('Capturing Light Mode - Dashboard Truth...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'qa_prompt_studio_light_truth.png'),
    fullPage: true
  });

  // Switch to Custom Topic mode
  console.log('Switching to Custom Topic mode...');
  await page.evaluate(() => {
    const tabBtns = Array.from(document.querySelectorAll('.source-tab-btn'));
    if (tabBtns[1]) tabBtns[1].click();
  });
  await new Promise(r => setTimeout(r, 800));

  // Screenshot Light Mode - Custom Topic
  console.log('Capturing Light Mode - Custom Topic...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'qa_prompt_studio_light_custom.png'),
    fullPage: true
  });

  // Toggle Dark Mode
  console.log('Toggling Dark Mode...');
  await page.click('.btn-theme-toggle');
  await new Promise(r => setTimeout(r, 800));

  // Screenshot Dark Mode - Custom Topic
  console.log('Capturing Dark Mode - Custom Topic...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'qa_prompt_studio_dark_custom.png'),
    fullPage: true
  });

  // Open Image Picker Modal
  console.log('Testing Image Picker Modal...');
  await page.evaluate(() => {
    const imgRadio = document.querySelectorAll('.pres-bg-card')[1];
    if (imgRadio) imgRadio.click();
  });
  await new Promise(r => setTimeout(r, 800));

  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'qa_image_picker_modal.png'),
    fullPage: true
  });

  // Close Image Picker Modal
  await page.evaluate(() => {
    const closeBtn = document.querySelector('.btn-close-modal, .modal-close-btn, button[aria-label="Close"]');
    if (closeBtn) closeBtn.click();
  });
  await new Promise(r => setTimeout(r, 500));

  // Audit accessibility issues on Prompt Studio
  const a11yIssues = await page.evaluate(() => {
    const issues = [];

    // Check all inputs have labels
    const inputs = Array.from(document.querySelectorAll('input, select, textarea'));
    inputs.forEach((input, i) => {
      const id = input.id;
      const ariaLabel = input.getAttribute('aria-label');
      const ariaLabelledby = input.getAttribute('aria-labelledby');
      const label = id ? document.querySelector(`label[for="${id}"]`) : input.closest('label');
      if (!ariaLabel && !ariaLabelledby && !label) {
        issues.push(`Input without accessible label: tag=${input.tagName}, id=${id}, name=${input.name}`);
      }
    });

    // Check all buttons have accessible names
    const buttons = Array.from(document.querySelectorAll('button'));
    buttons.forEach((btn, i) => {
      const text = btn.innerText?.trim();
      const ariaLabel = btn.getAttribute('aria-label');
      const title = btn.getAttribute('title');
      if (!text && !ariaLabel && !title) {
        issues.push(`Button without accessible name at index ${i}: class=${btn.className}`);
      }
    });

    // Check color contrasts or hidden overflows
    const elementsWithOverflow = [];
    document.querySelectorAll('*').forEach(el => {
      if (el.scrollWidth > el.clientWidth && el.clientWidth > 0 && !['HTML', 'BODY'].includes(el.tagName)) {
        const style = window.getComputedStyle(el);
        if (style.overflowX === 'visible' && !el.className.includes('scroll')) {
          elementsWithOverflow.push(`Overflow on ${el.tagName}.${el.className}: scrollWidth=${el.scrollWidth}, clientWidth=${el.clientWidth}`);
        }
      }
    });

    return { issues, elementsWithOverflow };
  });

  console.log('Console Logs count:', consoleLogs.length);
  console.log('Page Errors:', pageErrors);
  console.log('A11y Issues:', a11yIssues);

  await browser.close();
}

run().catch(err => {
  console.error('QA script failed:', err);
  process.exit(1);
});
