import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { build } from 'esbuild';
import { getSlideTheme } from '../src/theme/slideTokens.js';

const temporary = await mkdtemp(path.join(tmpdir(), 'presentation-content-'));
try {
  const outfile = path.join(temporary, 'views.mjs');
  await build({ stdin: {
    contents: `export { default as Layout } from './src/components/presentation/slides/SlideLayoutViews.jsx';
               export { default as Visual } from './src/components/presentation/visual/VisualSlideRenderer.jsx';
               export { ResolvedCanvas } from './src/components/presentation/slides/ResolvedSlideContent.jsx';`,
    resolveDir: process.cwd(), loader: 'jsx',
  }, outfile, bundle: true, platform: 'node', format: 'esm', packages: 'external',
  loader: { '.scss': 'empty', '.css': 'empty' } });
  // Resolve bundled dependencies from this project rather than the temp folder.
  const { symlink } = await import('node:fs/promises');
  await symlink(path.join(process.cwd(), 'node_modules'), path.join(temporary, 'node_modules'));
  const { Layout, Visual, ResolvedCanvas } = await import(pathToFileURL(outfile).href);
  const slide = { id: 'follow-up', title: 'What HR should confirm next', category: 'ATTENDANCE REVIEW',
    narrative: 'Confirm the WFO requirement before making a compliance decision.',
    bullets: ['Confirm the working-day calendar.'], metrics: [], business_report: true, order: 8, total_slides: 8 };
  for (const id of ['clean_light', 'executive_dark']) {
    const theme = getSlideTheme(id);
    const html = renderToStaticMarkup(React.createElement(Layout, { layout: 'comparison_split', slide, theme }));
    assert.ok(html.includes('working-day calendar'));
    assert.ok(!html.includes('Variance Mitigation'));
    assert.ok(!html.includes('Automated Governance'));
    assert.ok(!html.includes('0 - 30 Days'));
    const visual = renderToStaticMarkup(React.createElement(Visual, { slide, theme,
      visualSpec: { headline: slide.title, layout: { family: 'TEXT', variant: 'default' },
                    source_footer: { dataset_label: 'July attendance', confidence_statement: 'Audited Ground Truth (±0.1%)' } } }));
    assert.ok(visual.includes('Source: July attendance'));
    assert.ok(!visual.includes('Audited Ground Truth'));
    const table = { kind: 'table', x:48, y:150, width:864, height:120, size:16,
      headers:['Employee','Days'], rows:[['001','3'],['002','5']], column_widths:[432,432], row_heights:[40,40,40] };
    const plan = { width:960,height:540, pages:[[table],[{...table, rows:[['003','7']]}]] };
    const first = renderToStaticMarkup(React.createElement(ResolvedCanvas, { plan, theme, slide, slideIndex:6,totalSlides:8 }));
    const second = renderToStaticMarkup(React.createElement(ResolvedCanvas, { plan, theme, slide, part:1,reflow:true,slideIndex:6,totalSlides:8 }));
    assert.ok(first.includes('001') && first.includes('002') && first.includes('1/2'));
    assert.ok(second.includes('003') && !second.includes('001') && second.includes('2/2'));
    assert.ok(first.includes('font-size:16px') && first.includes('scope="col"'));
    assert.ok(second.includes('resolved-slide-reflow'));
    const chart = { kind:'chart', x:48,y:150,width:864,height:320, chart:{title:'Office days',unit:'days',categories:['Week 1'],series:[{name:'Days',values:[3.125]}]} };
    const accessible = renderToStaticMarkup(React.createElement(ResolvedCanvas, { plan:{...plan,pages:[[chart]]},theme,slide }));
    assert.ok(accessible.includes('resolved-chart-data') && accessible.includes('3.125') && accessible.includes('Office days (days)'));

  }
  console.log('Business slides: no invented priorities or audit marketing in either theme.');
} finally {
  await rm(temporary, { recursive: true, force: true });
}
