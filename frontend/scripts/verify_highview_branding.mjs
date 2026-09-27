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

  console.log('Navigating to HighView application...');
  await page.goto('http://localhost:5175', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));

  // 1. Audit Browser Tab Title & Metadata in Rendered HTML
  const audit = await page.evaluate(() => {
    const getMeta = (prop, isProperty = false) => {
      const el = document.querySelector(isProperty ? `meta[property="${prop}"]` : `meta[name="${prop}"]`);
      return el ? el.getAttribute('content') : null;
    };

    return {
      title: document.title,
      metaTitle: getMeta('title'),
      metaDescription: getMeta('description'),
      metaKeywords: getMeta('keywords'),
      appName: getMeta('application-name'),
      appleTitle: getMeta('apple-mobile-web-app-title'),
      ogTitle: getMeta('og:title', true),
      ogDescription: getMeta('og:description', true),
      ogSiteName: getMeta('og:site_name', true),
      twitterTitle: getMeta('twitter:title'),
      twitterDescription: getMeta('twitter:description'),
      headerTitle: document.querySelector('.brand-group h1')?.innerText,
      headerAttribution: document.querySelector('.brand-ai-attribution')?.innerText,
      headerSubtitle: document.querySelector('.brand-group .subtitle')?.innerText,
      heroTitle: document.querySelector('.adaptive-page-title')?.innerText,
      heroBadge: document.querySelector('.adaptive-hero-badge')?.innerText,
      heroTagline: document.querySelector('.adaptive-page-tagline')?.innerText,
      footerCopy: document.querySelector('.footer-copy')?.innerText,
    };
  });

  console.log('--- METADATA & UI AUDIT ---');
  console.log(JSON.stringify(audit, null, 2));

  // 2. Capture Homepage Hero & Header
  console.log('Capturing HighView Homepage Hero...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_highview_homepage_hero.png')
  });

  // 3. Scroll to Footer and Capture
  console.log('Capturing HighView Footer...');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await new Promise(r => setTimeout(r, 600));
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_highview_footer.png')
  });

  // 4. Test Mobile / PWA Viewport
  console.log('Capturing HighView Mobile Viewport (390px)...');
  await page.setViewport({ width: 390, height: 844 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await new Promise(r => setTimeout(r, 600));
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_highview_mobile.png')
  });

  // 5. Test Presentation Studio Branding
  await page.setViewport({ width: 1440, height: 950 });
  console.log('Navigating to Presentation Studio...');
  await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('nav button, .tabs-nav-segmented button'));
    const pBtn = btns.find(b => b.innerText.includes('Presentation'));
    if (pBtn) pBtn.click();
  });
  await new Promise(r => setTimeout(r, 1500));

  console.log('Capturing HighView Presentation Studio View...');
  await page.screenshot({
    path: path.join(ARTIFACT_DIR, 'verify_highview_presentation_studio.png')
  });

  await browser.close();
  console.log('HighView verification completed successfully!');
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
