import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { build } from 'esbuild';
import React from 'react';
import { floatingPosition } from '../src/components/presentation/floatingPosition.js';

// Exercise the actual hook and page with controlled API promises. This small
// dispatcher provides state, dependency comparison and effect cleanup without
// requiring a DOM; browser rendering is a separate verification step.
const internals = React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
function mount(render, props = {}, commit = () => {}) {
  const cells = [];
  let cursor = 0, pending = [], dirty = true, value;
  const changed = (a, b) => !a || !b || a.length !== b.length || a.some((item, i) => !Object.is(item, b[i]));
  const dispatcher = {
    useState(initial) {
      const index = cursor++;
      if (!cells[index]) cells[index] = { value: typeof initial === 'function' ? initial() : initial };
      return [cells[index].value, next => {
        const updated = typeof next === 'function' ? next(cells[index].value) : next;
        if (!Object.is(updated, cells[index].value)) { cells[index].value = updated; dirty = true; }
      }];
    },
    useRef(initial) { const index = cursor++; return (cells[index] ||= { current: initial }); },
    useId() { const index = cursor++; return (cells[index] ||= { value: `test-id-${index}` }).value; },
    useCallback(fn, deps) {
      const index = cursor++;
      if (!cells[index] || changed(cells[index].deps, deps)) cells[index] = { value: fn, deps };
      return cells[index].value;
    },
    useEffect(fn, deps) {
      const index = cursor++;
      if (!cells[index] || changed(cells[index].deps, deps)) {
        const previous = cells[index];
        cells[index] = { deps, cleanup: previous?.cleanup };
        pending.push(() => { previous?.cleanup?.(); cells[index].cleanup = fn(); });
      }
    },
  };
  dispatcher.useLayoutEffect = dispatcher.useEffect;
  function flush() {
    for (let count = 0; dirty; count++) {
      assert.ok(count < 30, 'render settles');
      cursor = 0; dirty = false;
      const previous = internals.ReactCurrentDispatcher.current;
      internals.ReactCurrentDispatcher.current = dispatcher;
      try { value = render(props); } finally { internals.ReactCurrentDispatcher.current = previous; }
      commit(value);
      const effects = pending; pending = []; effects.forEach(effect => effect());
    }
    return value;
  }
  return {
    get value() { return flush(); },
    props(next) { props = { ...props, ...next }; dirty = true; return flush(); },
    async settle() { for (let i = 0; i < 8; i++) { await Promise.resolve(); flush(); } return value; },
    unmount() { cells.forEach(cell => cell.cleanup?.()); },
  };
}
function find(node, predicate) {
  if (!React.isValidElement(node)) return null;
  if (predicate(node)) return node;
  for (const child of React.Children.toArray(node.props.children)) {
    const found = find(child, predicate); if (found) return found;
  }
  return null;
}
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const require = createRequire(import.meta.url);
const frontendRoot = fileURLToPath(new URL('../', import.meta.url));
const temporary = await mkdtemp(path.join(tmpdir(), 'deck-controls-'));
const apiNames = ['getPresentationThemes', 'startPresentationGeneration', 'getPresentationJob', 'getPresentationDeck', 'cancelPresentationJob', 'getSheets', 'updatePresentationDeck', 'regenerateSlide', 'exportPresentationPptx', 'previewPresentationScope', 'getAdaptiveDashboardPrimaryElement', 'getLatestPresentationDeck', 'deletePresentationDeck', 'getDatasetPersonas'];
const api = Object.fromEntries(apiNames.map(name => [name, async () => ({})]));
api.getPresentationJob = () => new Promise(() => {});
api.getPresentationThemes = async () => ({ themes: [] });
api.getSheets = async () => ({ sheets: [] });
globalThis.__deckControlTestApi = api;
globalThis.window = { location: { search: '' } };
globalThis.sessionStorage = { getItem: () => null };
let suites = 0;
try {
  const bundle = path.join(temporary, 'workflow.mjs');
  await build({
    stdin: { contents: `export {usePresentationWorkflow} from './src/components/presentation/usePresentationWorkflow.js'; export {default as PresentationPage} from './src/pages/PresentationPage.jsx'; export {default as DeckFloatingLayer} from './src/components/presentation/DeckFloatingLayer.jsx'; export {default as DeckControl} from './src/components/presentation/DeckControl.jsx';`, resolveDir: frontendRoot, loader: 'jsx' },
    outfile: bundle, bundle: true, platform: 'node', format: 'esm', loader: { '.scss': 'empty' },
    plugins: [{ name: 'test-api', setup(builder) {
      builder.onResolve({ filter: /^(react|lucide-react)$/ }, args => ({ path: require.resolve(args.path), external: true }));
      builder.onResolve({ filter: /^react-dom$/ }, () => ({ path: 'portal', namespace: 'mock' }));
      builder.onResolve({ filter: /api\/client$/ }, () => ({ path: 'api', namespace: 'mock' }));
      builder.onResolve({ filter: /standaloneHtmlExporter$/ }, () => ({ path: 'exporter', namespace: 'mock' }));
      builder.onResolve({ filter: /components\/(EvidenceInspectionDrawer|presentation\/(DeckGeneratingView|DeckStudioView|PromptStudioScreen|SlideRegenModal|PresentationPageHeader))\.jsx$/ }, args => ({ path: path.basename(args.path, '.jsx'), namespace: 'mock' }));
      builder.onLoad({ filter: /.*/, namespace: 'mock' }, args => ({ contents: args.path === 'api'
        ? apiNames.map(name => `export const ${name}=(...args)=>globalThis.__deckControlTestApi.${name}(...args);`).join('\n')
        : args.path === 'portal' ? 'export const createPortal=(element,target)=>({...element,portalTarget:target});'
        : args.path === 'exporter' ? 'export const exportStandaloneHtmlPresentation=()=>{};'
          : `export default function ${args.path}(){return null;}`, loader: 'js' }));
    } }],
  });
  const { usePresentationWorkflow, PresentationPage, DeckFloatingLayer, DeckControl } = await import(pathToFileURL(bundle));
  const oldDeck = { id: 21, slides: [{ title: 'Previous deck' }] };
  {
    const runner = mount(usePresentationWorkflow, { isOpen: true, initialDeck: oldDeck, activeJobId: 'old-job' });
    assert.equal(runner.value.viewMode, 'studio');
    runner.value.handleNewDeck();
    assert.equal(runner.value.viewMode, 'config');
    assert.equal(runner.value.configSession, 1);
    assert.equal(runner.value.currentJobId, null);
    assert.equal(runner.value.deckSpec.id, oldDeck.id, 'Return to Deck preserves the prior deck');
    runner.props({ initialDeck: { ...oldDeck } });
    assert.equal(runner.value.viewMode, 'config', 'parent refresh of the old deck must not close New Deck');
    runner.props({ initialDeck: null });
    assert.equal(runner.value.viewMode, 'config', 'old job must not restart when old deck prop is cleared');
    runner.props({ initialDeck: { id: 22, slides: [] } });
    assert.equal(runner.value.viewMode, 'studio', 'a genuinely different external deck still opens');
    runner.unmount(); suites++;
  }
  {
    const runner = mount(PresentationPage, { initialDeck: oldDeck });
    const prompt = () => find(runner.value, element => element.type?.name === 'PromptStudioScreen');
    const header = () => find(runner.value, element => element.type?.name === 'PresentationPageHeader');
    const originalKey = prompt().key;
    header().props.onGoBackToConfig();
    assert.equal(header().props.viewMode, 'config');
    assert.notEqual(prompt().key, originalKey, 'New Deck remounts the guided form at step 1');
    const freshKey = prompt().key;
    header().props.onReturnToDeck();
    assert.equal(header().props.viewMode, 'studio');
    assert.equal(prompt().key, freshKey, 'Return to Deck keeps the new draft');
    runner.unmount(); suites++;
  }
  {
    window.location.search = '?deck_id=21';
    const request = deferred();
    api.getPresentationDeck = () => request.promise;
    const runner = mount(usePresentationWorkflow, { isOpen: true });
    runner.value.handleNewDeck();
    request.resolve({ deck: oldDeck });
    await runner.settle();
    assert.equal(runner.value.viewMode, 'config', 'late URL load must not overwrite New Deck');
    assert.equal(runner.value.deckSpec, null);
    runner.unmount(); window.location.search = ''; suites++;
  }
  {
    const request = deferred();
    api.startPresentationGeneration = () => request.promise;
    const updates = [];
    const runner = mount(usePresentationWorkflow, { isOpen: true, onJobUpdate: job => updates.push(job) });
    const start = runner.value.handleStartGeneration({ objective: 'Fresh deck' });
    assert.equal(runner.value.viewMode, 'generating');
    await runner.value.handleCancelGeneration();
    assert.equal(runner.value.viewMode, 'config');
    request.resolve({ job_id: 'late-job' }); await start; await runner.settle();
    assert.equal(runner.value.viewMode, 'config', 'cancelled startup must not reopen generation');
    assert.equal(runner.value.currentJobId, null);
    assert.deepEqual(updates, []);
    runner.unmount(); suites++;
  }
  {
    const job = deferred();
    const generatedDeck = { id: 30, slides: [{ title: 'New generated deck' }] };
    let payload;
    api.startPresentationGeneration = async scope => { payload = scope; return { job_id: 'new-job' }; };
    api.getPresentationJob = () => job.promise;
    let runner;
    const updateParent = update => runner.props({
      activeJobId: update.job_id || update.id,
      initialDeck: update.status === 'in_progress' ? null : update.deck || null,
    });
    runner = mount(usePresentationWorkflow, { isOpen: true, initialDeck: oldDeck, onJobUpdate: updateParent });
    runner.value.handleNewDeck();
    await runner.value.handleStartGeneration({ objective: 'New briefing', themeId: 'clean_light' });
    assert.equal(runner.value.viewMode, 'generating');
    assert.equal(runner.value.currentJobId, 'new-job');
    assert.equal(payload.objective, 'New briefing');
    assert.equal(payload.theme_id, 'clean_light');
    job.resolve({ id: 'new-job', status: 'ready', progress_pct: 100, deck: generatedDeck });
    await runner.settle();
    assert.equal(runner.value.viewMode, 'studio', 'normal generation still opens its completed deck');
    assert.equal(runner.value.deckSpec.id, generatedDeck.id);
    runner.unmount(); suites++;
  }
  {
    for (const viewport of [{ width: 1280, height: 720 }, { width: 375, height: 667 }, { width: 320, height: 360, top: 40, left: 10 }]) {
      for (const anchor of [
        { left: viewport.left || 0, top: viewport.top || 0, width: 44, bottom: (viewport.top || 0) + 44 },
        { left: (viewport.left || 0) + viewport.width - 44, top: (viewport.top || 0) + viewport.height - 44, width: 44, bottom: (viewport.top || 0) + viewport.height },
        { left: viewport.width / 2, top: viewport.height / 2, width: 44, bottom: viewport.height / 2 + 44 },
      ]) {
        for (const placement of ['top', 'bottom']) for (const popup of [{ width: 220, height: 36 }, { width: 480, height: 500 }]) {
          const p = floatingPosition(anchor, popup, viewport, placement);
          assert.ok(p.left >= (viewport.left || 0) + 12);
          assert.ok(p.top >= (viewport.top || 0) + 12);
          assert.ok(p.left + Math.min(popup.width, p.maxWidth) <= (viewport.left || 0) + viewport.width - 12);
          assert.ok(p.top + Math.min(popup.height, p.maxHeight) <= (viewport.top || 0) + viewport.height - 12);
        }
      }
    }
    assert.equal(floatingPosition({ left: 40, top: 4, width: 44, bottom: 48 }, { width: 220, height: 36 }, { width: 375, height: 667 }).top, 56, 'tooltip flips below controls near the top edge');
    const p = floatingPosition({ left: 40, top: 600, width: 44, bottom: 644 }, { width: 220, height: 100 }, { width: 375, height: 667 }, 'bottom');
    assert.equal(p.top, 492, 'popover flips above near the bottom edge');
    suites++;
  }
  {
    // Verify layer lifecycle and keyboard behavior against controlled DOM bounds.
    // The actual browser top-layer paint behavior still needs visual verification.
    const listeners = new Map();
    const eventTarget = target => ({
      addEventListener(name, fn) { listeners.set(`${target}:${name}`, fn); },
      removeEventListener(name) { listeners.delete(`${target}:${name}`); },
    });
    Object.assign(window, eventTarget('window'), { innerWidth: 375, innerHeight: 667 });
    globalThis.document = { ...eventTarget('document'), body: {}, fullscreenElement: null, activeElement: null };
    const anchor = { getBoundingClientRect: () => ({ left: 20, top: 4, width: 44, bottom: 48 }), contains: () => false,
      focus: () => { document.activeElement = anchor; } };
    let visible = false;
    const items = [0, 1].map(i => ({ focus: () => {
      assert.ok(visible, 'the panel must be visible before focusing its controls');
      document.activeElement = items[i];
    } }));
    let shown = false, closed = 0;
    const layer = { offsetWidth: 220, offsetHeight: 100, scrollHeight: 100, clientHeight: 100,
      showPopover: () => { shown = true; }, hidePopover: () => { shown = false; }, matches: () => shown,
      querySelectorAll: () => items, querySelector: () => items[0], contains: () => false };
    const props = { anchorRef: { current: anchor }, onClose: () => closed++, role: 'dialog', placement: 'bottom' };
    const commitLayer = node => { node.ref.current = layer; visible = node.props.style.visibility === 'visible'; };
    const runner = mount(DeckFloatingLayer, props, commitLayer);
    assert.equal(runner.value.props.popover, 'manual', 'overlay uses the browser top layer');
    assert.equal(runner.value.portalTarget, document.body, 'popup is portaled out of overflow containers');
    assert.equal(runner.value.props.style.top, 56);
    let stopped = 0;
    for (const name of ['onWheel', 'onTouchStart', 'onTouchEnd']) runner.value.props[name]({ stopPropagation: () => stopped++ });
    assert.equal(stopped, 3, 'scrolling a popup must not trigger deck swipe or wheel navigation');
    assert.equal(document.activeElement, items[0], 'dialog focuses its first control');
    const key = { key: 'Tab', shiftKey: true, preventDefault() {}, stopPropagation() {} };
    listeners.get('document:keydown')(key);
    assert.equal(document.activeElement, items[1], 'keyboard focus stays within the suggestions');
    listeners.get('document:keydown')({ ...key, key: 'Escape' });
    assert.equal(closed, 1);
    assert.equal(document.activeElement, anchor, 'Escape restores trigger focus');
    listeners.get('document:pointerdown')({ target: {} });
    assert.equal(closed, 2, 'outside clicks dismiss the panel');
    runner.unmount();
    assert.equal(shown, false, 'top layer is removed during cleanup');
    assert.equal(listeners.size, 0, 'overlay listeners are cleaned up');
    document.fullscreenElement = {};
    const fullscreen = mount(DeckFloatingLayer, { ...props, role: 'tooltip' }, commitLayer);
    assert.equal(fullscreen.value.portalTarget, document.fullscreenElement, 'fullscreen remains the portal host');
    listeners.get('document:fullscreenchange')();
    assert.equal(closed, 3, 'fullscreen transitions dismiss stale positioning');
    fullscreen.unmount();
    // Older browsers use the same unclipped portal without the Popover API.
    delete layer.showPopover; delete layer.hidePopover;
    const fallback = mount(DeckFloatingLayer, props, commitLayer);
    assert.equal(fallback.value.props.style.visibility, 'visible');
    fallback.unmount(); suites++;
  }
  {
    const button = React.createElement('button', { 'aria-label': 'Edit' }, 'Edit');
    const help = React.createElement('span', { className: 'symbolic-tooltip' }, 'Inline editing');
    const runner = mount(DeckControl, { className: 'symbolic-btn-wrap', children: [button, help] });
    assert.equal(find(runner.value, element => element.type === 'span'), null, 'help is removed from the clipped wrapper');
    runner.value.props.onFocus({ target: { matches: () => true } });
    const floating = find(runner.value, element => element.type === DeckFloatingLayer);
    assert.equal(floating.props.children, 'Inline editing');
    assert.equal(find(runner.value, element => element.type === 'button').props['aria-describedby'], floating.props.id, 'focused control is associated with floating help');
    floating.props.onClose();
    assert.equal(find(runner.value, element => element.type === DeckFloatingLayer), null, 'dismissed tooltip stays closed until retriggered');
    runner.unmount(); suites++;
  }
  console.log(`Deck controls: ${suites} regression suites passed (navigation, form reset, async cancellation and 36 viewport combinations).`);
} finally {
  delete globalThis.__deckControlTestApi; delete globalThis.window; delete globalThis.sessionStorage; delete globalThis.document;
  await rm(temporary, { recursive: true, force: true });
}
