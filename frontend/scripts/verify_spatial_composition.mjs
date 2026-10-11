import puppeteer from 'puppeteer';

const ARTIFACT_DIR = '/Users/vinayksharma/.gemini/antigravity/brain/8b03f9e3-5aca-46a9-9b30-abe2f5add822';

async function verify() {
  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  console.log("=================================================");
  console.log("1. VERIFYING WORKFORCE DATASET 99767 (DESKTOP 1440px)");
  console.log("=================================================");
  await page.setViewport({ width: 1440, height: 1100, deviceScaleFactor: 2 });
  await page.goto('http://localhost:5175/?dataset_id=99767#dashboard', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 2000));

  const wfResult = await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('.executive-visual-card')).map(el => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return {
        testId: el.getAttribute('data-testid'),
        colSpan: el.getAttribute('data-column-span') || el.style.gridColumn,
        heightClass: el.getAttribute('data-height-class'),
        className: el.className,
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        gridColumn: style.gridColumn,
        title: el.querySelector('h3')?.innerText?.trim(),
        section: el.closest('section')?.getAttribute('aria-labelledby'),
      };
    });

    const sections = Array.from(document.querySelectorAll('.dashboard-section--priority, .dashboard-section--diagnostics, .dashboard-section--supporting')).map(sec => {
      const secCards = Array.from(sec.querySelectorAll('.executive-visual-card')).map(c => ({
        title: c.querySelector('h3')?.innerText?.trim(),
        span: c.getAttribute('data-column-span'),
        heightClass: c.getAttribute('data-height-class'),
      }));
      return {
        id: sec.getAttribute('aria-labelledby'),
        cardCount: secCards.length,
        cards: secCards,
      };
    });

    return { cards, sections };
  });

  console.log(`\nFound ${wfResult.cards.length} cards across ${wfResult.sections.length} visual sections:`);
  wfResult.sections.forEach(s => {
    console.log(`\nSection [${s.id}] - ${s.cardCount} cards:`);
    s.cards.forEach(c => {
      console.log(`  - "${c.title}" -> span: ${c.span}, height: ${c.heightClass}`);
    });
  });

  await page.screenshot({
    path: `${ARTIFACT_DIR}/desktop_workforce_spatial_composition_99767.png`,
    fullPage: true,
  });
  console.log(`\nSaved screenshot: ${ARTIFACT_DIR}/desktop_workforce_spatial_composition_99767.png`);

  console.log("\n=================================================");
  console.log("2. VERIFYING TABLET VIEWPORT (1024px)");
  console.log("=================================================");
  await page.setViewport({ width: 1024, height: 900, deviceScaleFactor: 2 });
  await new Promise(r => setTimeout(r, 1000));

  const tabletSpans = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.executive-visual-card')).map(el => {
      const style = window.getComputedStyle(el);
      return {
        title: el.querySelector('h3')?.innerText?.trim(),
        gridColumn: style.gridColumn,
        width: Math.round(el.getBoundingClientRect().width),
      };
    });
  });

  console.log("Tablet responsive spans (first 4 cards):");
  tabletSpans.slice(0, 4).forEach(c => {
    console.log(`  - "${c.title}": gridColumn=${c.gridColumn}, width=${c.width}px`);
  });

  await page.screenshot({
    path: `${ARTIFACT_DIR}/tablet_workforce_spatial_composition_1024px.png`,
    fullPage: true,
  });
  console.log(`Saved screenshot: ${ARTIFACT_DIR}/tablet_workforce_spatial_composition_1024px.png`);

  console.log("\n=================================================");
  console.log("3. VERIFYING MOBILE VIEWPORT (390px)");
  console.log("=================================================");
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2 });
  await new Promise(r => setTimeout(r, 1000));

  const mobileSpans = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('.executive-visual-card')).map(el => {
      const style = window.getComputedStyle(el);
      return {
        title: el.querySelector('h3')?.innerText?.trim(),
        gridColumn: style.gridColumn,
        width: Math.round(el.getBoundingClientRect().width),
      };
    });
  });

  console.log("Mobile responsive spans (first 3 cards):");
  mobileSpans.slice(0, 3).forEach(c => {
    console.log(`  - "${c.title}": gridColumn=${c.gridColumn}, width=${c.width}px`);
  });

  await page.screenshot({
    path: `${ARTIFACT_DIR}/mobile_workforce_spatial_composition_390px.png`,
    fullPage: true,
  });
  console.log(`Saved screenshot: ${ARTIFACT_DIR}/mobile_workforce_spatial_composition_390px.png`);

  console.log("\n=================================================");
  console.log("4. VERIFYING ENVIRONMENTAL DATASET 99768 (DESKTOP 1440px)");
  console.log("=================================================");
  await page.setViewport({ width: 1440, height: 1100, deviceScaleFactor: 2 });
  await page.goto('http://localhost:5175/?dataset_id=99768#dashboard', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.executive-visual-card', { timeout: 15000 });
  await new Promise(r => setTimeout(r, 2000));

  const envResult = await page.evaluate(() => {
    const sections = Array.from(document.querySelectorAll('.dashboard-section--priority, .dashboard-section--diagnostics, .dashboard-section--supporting')).map(sec => {
      const secCards = Array.from(sec.querySelectorAll('.executive-visual-card')).map(c => ({
        title: c.querySelector('h3')?.innerText?.trim(),
        span: c.getAttribute('data-column-span'),
        heightClass: c.getAttribute('data-height-class'),
      }));
      return {
        id: sec.getAttribute('aria-labelledby'),
        cardCount: secCards.length,
        cards: secCards,
      };
    });
    return { sections };
  });

  console.log(`\nEnvironmental sections (${envResult.sections.length}):`);
  envResult.sections.forEach(s => {
    console.log(`\nSection [${s.id}] - ${s.cardCount} cards:`);
    s.cards.forEach(c => {
      console.log(`  - "${c.title}" -> span: ${c.span}, height: ${c.heightClass}`);
    });
  });

  await page.screenshot({
    path: `${ARTIFACT_DIR}/desktop_environmental_spatial_composition_99768.png`,
    fullPage: true,
  });
  console.log(`Saved screenshot: ${ARTIFACT_DIR}/desktop_environmental_spatial_composition_99768.png`);

  await browser.close();
  console.log("\n>>> ALL MULTI-VIEWPORT & DATASET SPATIAL COMPOSITION VERIFICATIONS COMPLETE! <<<");
}

verify().catch(err => {
  console.error("Verification failed:", err);
  process.exit(1);
});
