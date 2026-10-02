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

  const ready = render({ jobStage: 'ready', jobProgress: 100 });
  assert.ok(ready.includes('Open in Studio'));
  assert.ok(ready.includes('Download .PPTX'));
  console.log('Presentation recovery: automatic rebuild, failed-state controls, and ready-state controls passed.');
} finally {
  await rm(temporary, { recursive: true, force: true });
}
