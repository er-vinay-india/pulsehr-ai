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
  await page.setViewport({ width: 1440, height: 950, deviceScaleFactor: 2 });

  console.log('--- 1. AUDITING DASHBOARD PAGE ---');
  await page.goto('http://localhost:5175#adaptive', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1500));

  const dashboardAudit = await page.evaluate(() => {
    const pageHeader = document.querySelector('.adaptive-dashboard-page .page-top-header');
    const title = pageHeader?.querySelector('.page-heading')?.innerText;
    const desc = pageHeader?.querySelector('.page-description')?.innerText;
    const hasDuplicateLogo = !!pageHeader?.querySelector('.hero-logo-img');
    const hasDuplicateHighviewH1 = pageHeader?.querySelector('.adaptive-page-title')?.innerText?.includes('HighView');
    const scopeBar = document.querySelector('.adaptive-scope-bar');

    return {
      title,
      desc,
      hasDuplicateLogo,
      hasDuplicateHighviewH1,
      hasScopeBar: !!scopeBar
    };
  });
  console.log('Dashboard Audit:', JSON.stringify(dashboardAudit, null, 2));

  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_page_dashboard_top.png'),
    clip: { x: 0, y: 0, width: 1440, height: 450 }
  });
  console.log('Captured verify_page_dashboard_top.png');

  console.log('--- 2. AUDITING DATA EXPLORER PAGE ---');
  await page.goto('http://localhost:5175#explorer', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1500));

  const explorerAudit = await page.evaluate(() => {
    const pageHeader = document.querySelector('.explorer-page .page-top-header');
    const title = pageHeader?.querySelector('.page-heading')?.innerText;
    const desc = pageHeader?.querySelector('.page-description')?.innerText;
    const toggleBtns = Array.from(pageHeader?.querySelectorAll('.toggle-btn') || []).map(b => b.innerText);
    const toolbar = document.querySelector('.explorer-compact-toolbar');

    return {
      title,
      desc,
      toggleBtns,
      hasToolbar: !!toolbar
    };
  });
  console.log('Explorer Audit:', JSON.stringify(explorerAudit, null, 2));

  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_page_explorer_top.png'),
    clip: { x: 0, y: 0, width: 1440, height: 450 }
  });
  console.log('Captured verify_page_explorer_top.png');

  console.log('--- 3. AUDITING PRESENTATION STUDIO PAGE ---');
  await page.goto('http://localhost:5175#presentation', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1500));

  const presentationAudit = await page.evaluate(() => {
    const pageHeader = document.querySelector('.presentation-page-container .page-top-header');
    const title = pageHeader?.querySelector('.page-heading')?.innerText;
    const desc = pageHeader?.querySelector('.page-description')?.innerText;
    const shell = document.querySelector('.presentation-page-shell');

    return {
      title,
      desc,
      hasShell: !!shell
    };
  });
  console.log('Presentation Audit:', JSON.stringify(presentationAudit, null, 2));

  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_page_presentation_top.png'),
    clip: { x: 0, y: 0, width: 1440, height: 500 }
  });
  console.log('Captured verify_page_presentation_top.png');

  console.log('--- 4. AUDITING FOOTER ON DESKTOP & MOBILE ---');
  const footerAudit = await page.evaluate(() => {
    const footer = document.querySelector('.app-footer');
    const brandTagline = footer?.querySelector('.footer-brand-tagline')?.innerText;
    const copyright = footer?.querySelector('.footer-copyright')?.innerText;
    const poweredBy = footer?.querySelector('.footer-powered-by')?.innerText;
    const fullText = footer?.innerText;
    const hasObsoleteLine = fullText?.includes('Automated spreadsheet analysis · Executive insights');

    return {
      brandTagline,
      copyright,
      poweredBy,
      hasObsoleteLine
    };
  });
  console.log('Footer Audit:', JSON.stringify(footerAudit, null, 2));

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await new Promise(r => setTimeout(r, 500));

  const footerElem = await page.$('.app-footer');
  if (footerElem) {
    await footerElem.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_footer_desktop.png')
    });
    console.log('Captured verify_footer_desktop.png');
  }

  // Mobile Footer Check (390 x 844)
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true });
  await new Promise(r => setTimeout(r, 500));
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const mobileFooterElem = await page.$('.app-footer');
  if (mobileFooterElem) {
    await mobileFooterElem.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_footer_mobile.png')
    });
    console.log('Captured verify_footer_mobile.png');
  }

  await browser.close();
  console.log('All verification tasks finished successfully!');
}

run().catch(err => {
  console.error('Error during verification:', err);
  process.exit(1);
});
