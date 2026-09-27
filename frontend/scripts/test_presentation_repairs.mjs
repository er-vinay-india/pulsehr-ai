import { build } from 'esbuild';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const result = await build({
  stdin: { contents: `
    import React from 'react';
    import {renderToStaticMarkup} from 'react-dom/server';
    import Deck from './src/components/FrontendSlidesDeck.jsx';
    import Slide from './src/components/PresentationSlideContent.jsx';
    import {buildSlideHtml} from './src/utils/exporter/slideHtmlBuilder';
    export {React, renderToStaticMarkup, Deck, Slide, buildSlideHtml};
  `, resolveDir: new URL('..', import.meta.url).pathname, loader: 'jsx' },
  bundle: true, write: false, platform: 'node', format: 'cjs', loader: { '.scss':'empty' },
});
const temp = mkdtempSync(join(tmpdir(), 'studio-ssr-'));
const output = join(temp,'bundle.cjs');
writeFileSync(output,result.outputFiles[0].text);
const {React, renderToStaticMarkup, Deck, Slide, buildSlideHtml} = createRequire(import.meta.url)(output);
rmSync(temp,{recursive:true});
const slides = [1,2,3].map(n => ({id:`s${n}`, title:`Slide ${n} title`, layout:'title_hero', bullets:['Verified finding'], narrative:'Source-based explanation', background_image:'https://images.unsplash.com/photo-test', scrim_opacity:65}));
const markup = renderToStaticMarkup(React.createElement(Deck, {slides,activeSlideIndex:1,deckId:'test',deckSpec:{id:'test'}}));
assert.equal((markup.match(/aria-roledescription="slide"/g)||[]).length, 1, 'Only the active slide mounts');
assert.ok(markup.includes('Slide 2 title'));
assert.ok(!markup.includes('Slide 1 title'));
assert.ok(!markup.includes('HRIDAY AI Heart'), 'Voice presenter must not appear in editor');
for (const slide of [slides[0], {...slides[0], visual_spec:{headline:'Visual headline', insights:['Finding']}}]) {
  const html = renderToStaticMarkup(React.createElement(Slide, {slide, theme:{bg_color:'#08111F'}}));
  assert.ok(html.includes('background-image:linear-gradient'));
  assert.ok(html.includes('images.unsplash.com/photo-test'));
}
const html = buildSlideHtml(slides[0],0,3,{slide_bg:'#08111F'});
assert.ok(html.includes('images.unsplash.com/photo-test'));
assert.ok(html.includes('0.65'));
console.log('Passed: active slide only, no editor voice orb, both renderer backgrounds, HTML background and scrim.');
