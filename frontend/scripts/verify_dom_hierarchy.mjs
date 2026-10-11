import puppeteer from 'puppeteer';

async function verify() {
  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1100, deviceScaleFactor: 2 });

  console.log("=================================================");
  console.log("VERIFYING WORKFORCE DATASET 99767 DOM HIERARCHY");
  console.log("=================================================");
  await page.goto('http://localhost:5175/?dataset_id=99767#dashboard', { waitUntil: 'networkidle2' });
  await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 2000));

  const wfResult = await page.evaluate(() => {
    const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => ({
      level: h.tagName,
      id: h.id || null,
      text: h.innerText.trim(),
      parentSection: h.closest('section, main, header, article, aside')?.tagName || null,
      parentSectionClass: h.closest('section, main, header, article, aside')?.className || null,
    }));

    const landmarks = Array.from(document.querySelectorAll('header, nav, main, section, aside, footer, article, figure, figcaption, dialog')).map(el => ({
      tag: el.tagName,
      className: el.className ? el.className.split(' ')[0] : '',
      ariaLabel: el.getAttribute('aria-label'),
      ariaLabelledby: el.getAttribute('aria-labelledby'),
      role: el.getAttribute('role'),
    }));

    const articles = Array.from(document.querySelectorAll('article.executive-visual-card')).map(a => ({
      testId: a.getAttribute('data-testid'),
      ariaLabelledby: a.getAttribute('aria-labelledby'),
      titleText: a.querySelector('h3')?.innerText?.trim(),
      hasFigure: Boolean(a.querySelector('figure')),
      hasFigcaption: Boolean(a.querySelector('figcaption')),
      hasInspectBtn: Boolean(a.querySelector('.card-btn-inspect')),
      hasDeepLink: Boolean(a.querySelector('.card-btn-deep-dive, .visual-card__deep-link')),
    }));

    return { headings, landmarksCount: landmarks.length, articles };
  });

  console.log("\n--- Headings Outline ---");
  wfResult.headings.forEach(h => {
    console.log(`  [${h.level}] "${h.text}" (in <${h.parentSection} class="${h.parentSectionClass?.split(' ')[0]}">)`);
  });

  console.log("\n--- Articles Count ---");
  console.log(`Total ExecutiveVisualCard articles: ${wfResult.articles.length}`);
  wfResult.articles.forEach(a => {
    console.log(`  - <article aria-labelledby="${a.ariaLabelledby}">: "${a.titleText}" [Figure: ${a.hasFigure}, Figcaption: ${a.hasFigcaption}, Inspect: ${a.hasInspectBtn}]`);
  });

  // Take screenshot
  const wfPath = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/desktop_workforce_dom_hierarchy_99767.png';
  await page.screenshot({ path: wfPath, fullPage: true });
  console.log(`\nSaved screenshot to ${wfPath}`);

  console.log("\n=================================================");
  console.log("VERIFYING ENVIRONMENTAL DATASET 99768 DOM HIERARCHY");
  console.log("=================================================");
  await page.goto('http://localhost:5175/?dataset_id=99768#dashboard', { waitUntil: 'networkidle2' });
  await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 2000));

  const envResult = await page.evaluate(() => {
    const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => ({
      level: h.tagName,
      id: h.id || null,
      text: h.innerText.trim(),
      parentSection: h.closest('section, main, header, article, aside')?.tagName || null,
      parentSectionClass: h.closest('section, main, header, article, aside')?.className || null,
    }));

    const articles = Array.from(document.querySelectorAll('article.executive-visual-card')).map(a => ({
      testId: a.getAttribute('data-testid'),
      titleText: a.querySelector('h3')?.innerText?.trim(),
      hasFigure: Boolean(a.querySelector('figure')),
      hasFigcaption: Boolean(a.querySelector('figcaption')),
    }));

    return { headings, articles };
  });

  console.log("\n--- Environmental Headings Outline ---");
  envResult.headings.forEach(h => {
    console.log(`  [${h.level}] "${h.text}" (in <${h.parentSection} class="${h.parentSectionClass?.split(' ')[0]}">)`);
  });

  console.log(`\nTotal Environmental articles: ${envResult.articles.length}`);
  envResult.articles.forEach(a => {
    console.log(`  - <article>: "${a.titleText}" [Figure: ${a.hasFigure}, Figcaption: ${a.hasFigcaption}]`);
  });

  const envPath = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822/desktop_environmental_dom_hierarchy_99768.png';
  await page.screenshot({ path: envPath, fullPage: true });
  console.log(`Saved screenshot to ${envPath}`);

  // Test Quick Inspect Dialog
  console.log("\n--- Testing Quick Inspect Dialog Accessibility ---");
  const firstInspectBtn = await page.$('.card-btn-inspect');
  if (firstInspectBtn) {
    await firstInspectBtn.click();
    await page.waitForSelector('dialog.quick-inspect-drawer', { timeout: 5000 });
    const dialogInfo = await page.evaluate(() => {
      const d = document.querySelector('dialog.quick-inspect-drawer');
      return {
        tagName: d.tagName,
        open: d.open,
        ariaModal: d.getAttribute('aria-modal'),
        ariaLabelledby: d.getAttribute('aria-labelledby'),
        title: d.querySelector('#inspect-dialog-title')?.innerText?.trim(),
        parentTag: d.parentElement.tagName,
        isBodyDirectChild: d.parentElement.parentElement === document.body,
      };
    });
    console.log("Dialog info:", dialogInfo);

    // Test ESC key closes dialog
    await page.keyboard.press('Escape');
    await new Promise(r => setTimeout(r, 500));
    const isClosed = await page.evaluate(() => !document.querySelector('dialog.quick-inspect-drawer'));
    console.log(`Dialog closed via Escape key: ${isClosed}`);
  }

  await browser.close();
  console.log("\nVerification complete!");
}

verify().catch(err => {
  console.error("Verification error:", err);
  process.exit(1);
});
