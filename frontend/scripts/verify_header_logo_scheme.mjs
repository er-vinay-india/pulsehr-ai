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
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

  console.log('Navigating to http://localhost:5175 ...');
  await page.goto('http://localhost:5175', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1500));

  // 1. Audit Desktop Header
  const desktopAudit = await page.evaluate(() => {
    const logoWrap = document.querySelector('.brand-group .brand-logo-wrap');
    const logoImg = document.querySelector('.brand-logo-img');
    const title = document.querySelector('.brand-group h1, .brand-group .brand-title');
    const subtitle = document.querySelector('.brand-group .subtitle');
    const headerHridayBadge = document.querySelector('.app-header .brand-ai-attribution');
    const footer = document.querySelector('.app-footer');
    
    const logoWrapStyle = logoWrap ? window.getComputedStyle(logoWrap) : null;
    const subtitleStyle = subtitle ? window.getComputedStyle(subtitle) : null;

    return {
      logoWrapExists: !!logoWrap,
      logoWrapBg: logoWrapStyle?.backgroundColor,
      logoWrapBorder: logoWrapStyle?.borderWidth + ' ' + logoWrapStyle?.borderStyle + ' ' + logoWrapStyle?.borderColor,
      logoWrapBoxShadow: logoWrapStyle?.boxShadow,
      logoImgSrc: logoImg?.src,
      titleText: title?.innerText,
      subtitleText: subtitle?.innerText,
      subtitleDisplay: subtitleStyle?.display,
      headerHridayBadgeExists: !!headerHridayBadge,
      footerText: footer?.innerText,
      footerHasHriday: footer?.innerText?.includes('HRIDAY')
    };
  });

  console.log('--- DESKTOP AUDIT RESULTS ---');
  console.log(JSON.stringify(desktopAudit, null, 2));

  // Screenshot Desktop Header Area
  const headerElem = await page.$('.app-header');
  if (headerElem) {
    await headerElem.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_header_desktop_clean.png')
    });
    console.log('Captured verify_header_desktop_clean.png');
  }

  // Screenshot Full Desktop Top Area
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_desktop_full_hero.png'),
    clip: { x: 0, y: 0, width: 1440, height: 750 }
  });
  console.log('Captured verify_desktop_full_hero.png');

  // 2. Audit Mobile Viewport (390 x 844)
  console.log('Switching to Mobile Viewport (390x844)...');
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await new Promise(r => setTimeout(r, 1000));

  const mobileAudit = await page.evaluate(() => {
    const logoWrap = document.querySelector('.brand-group .brand-logo-wrap');
    const subtitle = document.querySelector('.brand-group .subtitle');
    const logoWrapStyle = logoWrap ? window.getComputedStyle(logoWrap) : null;
    const subtitleStyle = subtitle ? window.getComputedStyle(subtitle) : null;

    return {
      subtitleText: subtitle?.innerText,
      subtitleDisplay: subtitleStyle?.display,
      subtitleVisibility: subtitleStyle?.visibility,
      subtitleColor: subtitleStyle?.color,
      subtitleFontSize: subtitleStyle?.fontSize,
      logoWrapBg: logoWrapStyle?.backgroundColor,
      logoWrapBorder: logoWrapStyle?.borderWidth + ' ' + logoWrapStyle?.borderStyle
    };
  });

  console.log('--- MOBILE AUDIT RESULTS ---');
  console.log(JSON.stringify(mobileAudit, null, 2));

  // Screenshot Mobile Header Area
  const mobileHeader = await page.$('.app-header');
  if (mobileHeader) {
    await mobileHeader.screenshot({
      path: path.join(ARTIFACT_DIR, 'verify_header_mobile_tagline_visible.png')
    });
    console.log('Captured verify_header_mobile_tagline_visible.png');
  }

  // Screenshot Full Mobile Screen
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_mobile_full_view.png')
  });
  console.log('Captured verify_mobile_full_view.png');

  // 3. Scroll to Footer on Mobile and capture
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_footer_mobile_hriday.png'),
    clip: { x: 0, y: 700, width: 390, height: 144 }
  });
  console.log('Captured verify_footer_mobile_hriday.png');

  await browser.close();
  console.log('Verification completed successfully!');
}

run().catch(err => {
  console.error('Error during verification:', err);
  process.exit(1);
});
