import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const temporary = await mkdtemp(path.join(tmpdir(), 'presentation-recovery-'));
try {
  const output = path.join(temporary, 'view.cjs');
  const bundle = await build({
    stdin: {
      contents: `export {default as React} from 'react';
        export {renderToStaticMarkup} from 'react-dom/server';
        export {default as View} from './src/components/presentation/DeckGeneratingView.jsx';
        export {STAGES} from './src/components/presentation/usePresentationWorkflow.js';`,
      resolveDir: fileURLToPath(new URL('../', import.meta.url)), loader: 'jsx',
    },
    bundle: true, write: false, platform: 'node', format: 'cjs',
  });
  await writeFile(output, bundle.outputFiles[0].text);
  const { React, renderToStaticMarkup, View, STAGES } = createRequire(import.meta.url)(output);
  const render = props => renderToStaticMarkup(React.createElement(View, {
    stages: STAGES, onOpenInStudio() {}, onExportPptx() {}, ...props,
  }));
  const recovery = render({
    jobStage: 'recovering', jobProgress: 0,
    jobStageLabel: 'Server reconnected. Rebuilding your presentation automatically…',
  });
  assert.ok(recovery.includes('Phase 1 of 13: Objective &amp; Brief Setup'));
  assert.ok(recovery.includes('Rebuilding your presentation automatically'));
  assert.ok(!recovery.includes('Generation Interrupted'));
  assert.ok(!recovery.includes('Open in Studio'));

  const failed = render({ jobStage: 'failed', jobProgress: 100, jobError: 'Evidence validation failed' });
  assert.ok(failed.includes('Evidence validation failed'));
  assert.ok(!failed.includes('Open in Studio'), 'a failed run at 100% must not offer a finished deck');
  assert.ok(!failed.includes('pipeline-stage-row completed'), 'failure must not certify every phase');
  assert.ok(!failed.includes('Download .PPTX'));
  assert.ok(failed.includes('Generation failed'));
  assert.ok(!failed.includes('spin-icon'), 'failed jobs must stop all loading animations');
  assert.ok(!failed.includes('100% Complete'), 'failed jobs must not advertise completion');
  assert.ok(!failed.includes('role="progressbar"'), 'a failed job is an error state, not an active loader');
  assert.ok(!failed.includes('pipeline-stages-list'), 'do not show pending phases under a terminal failure');
  assert.ok(failed.includes('aria-busy="false"'));
  assert.ok(failed.includes('Back to setup') && failed.includes('Try again'));

  const pending = render({ jobStage: 'export_qa', jobProgress: 100 });
  assert.ok(pending.includes('99% Complete'), '100 percent is reserved for a ready deck');
  const lastSlide = render({ jobStage: 'headlines', jobProgress: 45, slideProgressData: { current_slide: 3, total_slides: 3 } });
  assert.ok(lastSlide.includes('slide-step-pill building'), 'the last slide remains active until its phase finishes');

  const ready = render({ jobStage: 'ready', jobProgress: 100 });
  assert.ok(ready.includes('Open in Studio'));
  assert.ok(ready.includes('Download .PPTX'));
  console.log('Presentation recovery: automatic rebuild, failed-state controls, and ready-state controls passed.');
} finally {
  await rm(temporary, { recursive: true, force: true });
}
