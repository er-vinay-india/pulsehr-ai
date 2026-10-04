import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as sass from 'sass';
import { HRIDAYConversation } from '../src/components/hriday/conversation.js';
import { presentHRIDAYAnswer, inferHRIDAYTool, presentArtifacts } from '../src/components/hriday/presentation.js';
import { initialHRIDAYActivity, advanceHRIDAYActivity } from '../src/components/hriday/activity.js';
import { streamCopilotQuery } from '../src/api/client.js';
const delegates = [{ id: 'qwen', name: 'Qwen3.5', primary_model: 'qwen3.5', role_title: 'Chief Quantitative & Data Analytics Director' }];
const banner = '### 🏆 Elected Council Replier: **Qwen3.5**\n*Chief Quantitative & Data Analytics Director* — *Elected with 3/5 Council Votes (60% Quorum)*\n\n';
const greeting = 'Hello! I am Qwen3.5, serving as Chief Quantitative & Data Analytics Director on the HRIDAY Executive AI Council. Welcome to the War Room—how can I assist you with your datasets, workforce performance, or operational decisions today?';
const evidence = '**Attendance** is 87.5% across 259 records. [Evidence](https://example.com/report)';
function harness() {
  const calls = [];
  const c = new HRIDAYConversation((...args) => new Promise(resolve => calls.push({ args, cb: args[5], resolve })));
  return { c, calls };
}
test('chart payload and calculation context survive completion into the next turn', async () => {
  const { c, calls } = harness();
  const first = c.send('display me Cohort Average: Math Score');
  const prior = { sheet_id: 7, visualization_context: { metric: 'Math Score', operation: 'mean' } };
  calls[0].cb.onDone({ answer: 'Cohort average: 66.09', prior_context: prior });
  calls[0].resolve(); await first;
  const next = c.send('show me in chart format');
  assert.deepEqual(calls[1].args[7], prior);
  const chart = { chart_id: 'math', chart_type: 'column', categories: ['Cohort'], series: [{ name: 'Math Score', values: [66.09] }] };
  calls[1].cb.onDone({ answer: 'Here is the chart.', visual_charts: [chart], prior_context: prior });
  calls[1].resolve(); await next;
  assert.deepEqual(c.state.messages[3].visual_charts, [chart]);
  assert.equal(c.state.messages[3].phase, 'complete');
});
test('a chart-only response completes and singular chart fallback survives an empty chart list', async () => {
  const chart = { categories: ['Cohort'], series: [{ values: [66.09] }] };
  const c = new HRIDAYConversation(async (...args) => args[5].onDone({ visual_charts: [], visual_chart: chart }));
  await c.send('show chart');
  assert.equal(c.state.messages[1].phase, 'complete');
  assert.deepEqual(c.state.messages[1].visual_charts, [chart]);
});
test('model identity and council banner never flash at any streaming boundary', () => {
  for (const answer of [banner + evidence, banner + greeting, greeting, 'I cannot access live weather. As ' + delegates[0].role_title + ', ' + evidence, 'As ' + delegates[0].role_title + ', ' + evidence, 'From my perspective as ' + delegates[0].role_title + ', ' + evidence]) {
    for (let end = 1; end <= answer.length; end++) {
      const displayed = presentHRIDAYAnswer(answer.slice(0, end), { streaming: true, delegates });
      assert(!/Qwen|Elected|Quorum|Council|War Room|Chief Quantitative/i.test(displayed), displayed);
    }
  }
  assert.equal(presentHRIDAYAnswer('Hi! I am qwen. How can I help?', { delegates }), 'Hi, I’m HRIDAY. How can I help?');
  assert.equal(presentHRIDAYAnswer(banner + evidence, { delegates }), evidence);
  assert.equal(presentHRIDAYAnswer(banner + greeting, { delegates }), 'Hi, I’m HRIDAY. How can I help?');
  assert.equal(presentHRIDAYAnswer('I am concerned about attendance. Please explain.'), 'I am concerned about attendance. Please explain.');
});
test('one evolving answer preserves raw events, ballots, candidates and context internally', async () => {
  const { c, calls } = harness(); c.setDraft('Explain attendance');
  const pending = c.send(undefined, { scope: { sheetId: 42, snapshotId: 7 } }); const cb = calls[0].cb;
  cb.onWarRoomInit({ delegates }); const event = { type: 'candidate_answer', data: { answer: 'Internal' } }; cb.onEvent(event);
  cb.onDelegateVote({ delegate_id: 'qwen', vote: 'Internal vote' }); cb.onToken(banner); cb.onToken(evidence);
  assert.equal(c.state.messages.length, 2); assert.equal(c.state.messages[1].content, evidence);
  const result = { answer: banner + evidence, ballots: ['vote'], candidate_answers: ['candidates'], prior_context: { measure: 'attendance' } };
  cb.onDone(result); calls[0].resolve(); await pending;
  assert.equal(c.getDiagnostics(c.state.messages[1].id).result, result); assert.equal(c.getDiagnostics(c.state.messages[1].id).events[0], event);
  assert.equal(c.state.messages[1].phase, 'complete'); assert.equal(calls[0].args[4], 42); assert.equal(calls[0].args[8], 7);
});
test('duplicate submits blocked; Stop preserves partial answer and draft, ignores stale callbacks', async () => {
  const { c, calls } = harness(); const first = c.send('First'); await c.send('Duplicate'); assert.equal(calls.length, 1);
  calls[0].cb.onToken('Partial'); c.setDraft('Next'); c.stop();
  assert(calls[0].args[6].aborted); assert.equal(c.state.draft, 'Next'); assert.equal(c.state.messages[1].phase, 'stopped');
  const second = c.send(); calls[0].cb.onToken('Stale'); calls[0].cb.onDone({ answer: 'Stale' }); calls[0].cb.onError(new Error('Late'));
  assert.equal(c.state.messages[1].content, 'Partial'); assert(c.state.loading);
  calls[1].cb.onDone({ answer: 'Second' }); calls.forEach(call => call.resolve()); await Promise.all([first, second]);
  assert.equal(c.state.messages.length, 4); assert.equal(c.state.messages[3].content, 'Second');
});
test('retry keeps one question, original scope, draft; follow-up context resets on new conversation', async () => {
  const { c, calls } = harness(); const first = c.send('Question', { scope: { sheetId: 99 } });
  calls[0].cb.onToken('Partial'); calls[0].cb.onError(new Error('Technical credential detail')); calls[0].resolve(); await first;
  assert.equal(c.state.messages[1].phase, 'error'); assert(!JSON.stringify(c.state).includes('credential'));
  c.setDraft('Keep draft'); const retry = c.retry(c.state.messages[1]); assert.equal(c.state.messages.length, 2);
  assert.equal(calls[1].args[4], 99); assert.equal(c.state.draft, 'Keep draft');
  calls[1].cb.onDone({ answer: 'Recovered', prior_context: { scope: 'internal' } }); calls[1].resolve(); await retry;
  const next = c.send('Follow up'); assert.deepEqual(calls[2].args[7], { scope: 'internal' });
  c.newChat(); calls[2].cb.onDone({ answer: 'Late old answer' }); calls[2].resolve(); await next;
  assert.deepEqual(c.state.messages, []); assert.equal(c.priorContext, null);
});
test('unexpected EOF exposes recoverable incomplete state', async () => {
  const c = new HRIDAYConversation(async (...args) => args[5].onToken('Incomplete'));
  await c.send('Question'); assert.equal(c.state.messages[1].phase, 'error'); assert.equal(c.state.messages[1].content, 'Incomplete'); assert(!c.state.loading);
});
test('query tools preserve exact grammar and filters; artifact URLs stay local', () => {
  assert.deepEqual(inferHRIDAYTool('Calculate (12 + 8) / 4'), { name: 'arithmetic', expression: '(12 + 8) / 4' });
  assert.deepEqual(inferHRIDAYTool('Create a presentation'), { name: 'presentation' });
  assert.deepEqual(inferHRIDAYTool('Create a PPT'), { name: 'presentation' });
  assert.deepEqual(inferHRIDAYTool('Average attendance by department'), { name: 'calculate', calculation: { operation: 'mean', column: 'attendance_rate', group_by: 'department' } });
  assert.equal(inferHRIDAYTool('Average attendance in July for Sales'), null); assert.equal(inferHRIDAYTool('Explain the presentation process'), null);
  assert.equal(presentArtifacts([{ url: '/api/reports/presentation/files/deck.pptx' }, { url: 'javascript:alert(1)' }]).length, 1);
});
test('SSE preserves diagnostic events, split Unicode, CRLF, final completion; tools route through auto', async () => {
  const originalFetch = globalThis.fetch, requests = [];
  const bytes = new TextEncoder().encode('event: candidate_answer\r\ndata: {"answer":"internal"}\r\n\r\nevent: token\ndata: {"token":"HRIDAY’s answer"}\n\nevent: done\ndata: {"answer":"Ready"}');
  globalThis.fetch = async (url, options) => { requests.push(JSON.parse(options.body)); return new Response(new ReadableStream({ start(controller) {
    for (let start = 0; start < bytes.length; start += 3) controller.enqueue(bytes.slice(start, start + 3)); controller.close();
  } })); };
  try {
    const events = [], tokens = [], completions = [];
    const cb = { onEvent: e => events.push(e), onToken: t => tokens.push(t), onDone: r => completions.push(r), onError: e => { throw e; } };
    await streamCopilotQuery('Question', null, null, null, 42, cb);
    await streamCopilotQuery('2+3', null, { name: 'arithmetic', expression: '2+3' }, null, 42, cb);
    assert.equal(requests[0].engine, 'war_room'); assert.equal(requests[1].engine, 'auto');
    assert.equal(events[0].type, 'candidate_answer'); assert.equal(tokens[0], 'HRIDAY’s answer'); assert.equal(completions[0].answer, 'Ready');
  } finally { globalThis.fetch = originalFetch; }
});
test('chat references defined central theme tokens and has no independent palette or theme preference', () => {
  const source = readFileSync(new URL('../src/styles/hriday-chat.scss', import.meta.url), 'utf8');
  const tokens = sass.compile(new URL('../src/styles/_tokens.scss', import.meta.url).pathname).css;
  assert(!/#[\da-f]{3,8}\b|rgba?\(|hsla?\(/i.test(source));
  for (const [, token] of source.matchAll(/var\((--[\w-]+)/g)) if (!token.startsWith('--hriday-viewport-')) assert(tokens.includes(token + ':'), 'Unknown token: ' + token);
  const view = readFileSync(new URL('../src/components/hriday/HRIDAYChat.jsx', import.meta.url), 'utf8'); assert(!/Hruday|localStorage|ThemeToggle/.test(view));
});

test('loader follows real step signals, deduplicates mirrored candidates, hides model and voting details', () => {
  let activity = initialHRIDAYActivity();
  const received = [];
  const deliver = event => { activity = advanceHRIDAYActivity(activity, event); received.push(activity.text); };
  deliver({ type: 'war_room_init', data: { delegates: [1, 2, 3, 4, 5] } });
  for (let step = 1; step <= 5; step++) {
    deliver({ type: 'status', data: { phase: 1, step_index: step, step_count: 5, message: 'Qwen proposes an answer' } });
    assert.equal(activity.stepIndex, step);
    deliver({ type: 'candidate_answer', data: { delegate_id: 'private-' + step, candidate_answer: 'Raw private answer' } });
    const beforeMirror = activity;
    deliver({ type: 'delegate_perspective', data: { delegate_id: 'private-' + step, perspective: 'Raw private answer' } });
    assert.equal(activity, beforeMirror);
  }
  assert.equal(activity.approachIds.length, 5);
  deliver({ type: 'status', data: { phase: 2 } }); assert.equal(activity.text, 'Comparing possible answers…');
  for (let step = 1; step <= 5; step++) deliver({ type: 'delegate_vote', data: { delegate_id: 'private-' + step, vote: 'GPT-OSS wins' } });
  assert.equal(activity.text, 'The reviews are complete…');
  deliver({ type: 'status', data: { phase: 3 } }); assert.equal(activity.stage, 'composing');
  deliver({ type: 'token', data: { token: 'Answer' } }); assert.equal(activity.stage, 'writing');
  assert(received.includes('Considering another approach…'));
  assert(received.includes('Considering another angle…'));
  assert(!/Qwen|GPT|Council|private-|vote|quorum|5/.test(received.join(' ')));
});
test('unknown, duplicate and out-of-order activity cannot invent progress or rewind delivery', () => {
  let activity = initialHRIDAYActivity();
  const status = { type: 'status', data: { phase: 1, message: 'Phase 1: [2/5] Internal model' } };
  activity = advanceHRIDAYActivity(activity, status); assert.equal(activity.text, 'Considering another approach…');
  assert.equal(advanceHRIDAYActivity(activity, status), activity);
  assert.equal(advanceHRIDAYActivity(activity, { type: 'status', data: { phase: 'unknown', message: 'Invented progress' } }), activity);
  activity = advanceHRIDAYActivity(activity, { type: 'token', data: { token: 'Answer' } });
  assert.equal(advanceHRIDAYActivity(activity, status), activity);
  assert.equal(advanceHRIDAYActivity(activity, { type: 'candidate_answer', data: { delegate_id: 'late', candidate_answer: 'Late' } }), activity);
});
test('loader changes with tool and retrieval signals; stop and completion clear activity and ignore late signals', async () => {
  let activity = initialHRIDAYActivity();
  activity = advanceHRIDAYActivity(activity, { type: 'status', data: { phase: 'retrieval' } }); assert.equal(activity.stage, 'retrieving');
  const toolEvent = { type: 'status', data: { phase: 'tool' } };
  assert.equal(advanceHRIDAYActivity(activity, toolEvent, { name: 'arithmetic' }).text, 'Working through the calculation…');
  assert.equal(advanceHRIDAYActivity(activity, toolEvent, { name: 'presentation' }).text, 'Building your presentation…');
  const { c, calls } = harness(); const first = c.send('Explain');
  const initial = c.state.activity; c.setDraft('Draft while working'); assert.equal(c.state.activity, initial);
  calls[0].cb.onStatus({ phase: 1, step_index: 1, step_count: 5 });
  calls[0].cb.onEvent({ type: 'candidate_answer', data: { delegate_id: 'one', candidate_answer: 'Internal' } });
  assert.equal(c.state.status, 'An initial response is ready…');
  c.stop(); assert.equal(c.state.activity, null);
  calls[0].cb.onStatus({ phase: 2 }); calls[0].cb.onDelegateVote({ delegate_id: 'late' }); assert.equal(c.state.activity, null);
  calls[0].resolve(); await first;
  const second = c.send('Next'); calls[1].cb.onDone({ answer: 'Complete' }); assert.equal(c.state.activity, null);
  calls[1].resolve(); await second;
});

test('trusted product identity and truthful model disclosure survive presentation at every boundary', () => {
  const answer = "I'm HRIDAY, and this response is powered by qwen3.5:9b.";
  assert.equal(presentHRIDAYAnswer(answer, { delegates }), answer);
  for (let end = 1; end <= answer.length; end++) {
    const shown = presentHRIDAYAnswer(answer.slice(0, end), { streaming: true, delegates });
    assert(!shown.includes('Hi, I’m HRIDAY.'));
  }
  assert.equal(presentHRIDAYAnswer('DeepSeek and Qwen are models.', { delegates }), 'DeepSeek and Qwen are models.');
  assert.equal(presentHRIDAYAnswer("I'm Configured Assistant, powered by phi4.", { assistantName: 'Configured Assistant' }), "I'm Configured Assistant, powered by phi4.");
});

test('corrective reset keeps one answer and diagnostics, ignores stale reset callbacks', async () => {
  const { c, calls } = harness(); c.setIdentity({ name: 'Configured Assistant' });
  const pending = c.send('Question');
  assert.equal(c.state.activity.text, 'Connecting to Configured Assistant…');
  const cb = calls[0].cb;
  cb.onToken('Hello!'); cb.onReset({ reason: 'identity_validation' });
  assert.equal(c.state.messages.length, 2); assert.equal(c.state.messages[1].content, '');
  assert.equal(c.state.status, 'Refining your response…');
  cb.onToken('Corrected response.'); cb.onDone({ answer: 'Corrected response.', runtime_model: 'qwen3.5:9b', assistant_identity: { name: 'HRIDAY' } });
  assert.equal(c.state.messages[1].content, 'Corrected response.');
  cb.onReset({ reason: 'late' }); assert.equal(c.state.messages[1].content, 'Corrected response.');
  assert.equal(c.getDiagnostics(c.state.messages[1].id).result.runtime_model, 'qwen3.5:9b');
  calls[0].resolve(); await pending;
});

test('SSE dispatches a real corrective reset without hiding diagnostics', async () => {
  const saved = globalThis.fetch;
  globalThis.fetch = async () => new Response('event: answer_reset\ndata: {"reason":"identity_validation"}\n\nevent: done\ndata: {"answer":"Ready"}\n\n');
  try {
    const resets = [], events = [];
    await streamCopilotQuery('Question', null, null, null, null, { onReset: d => resets.push(d), onEvent: e => events.push(e) });
    assert.equal(resets.length, 1); assert.equal(events[0].type, 'answer_reset');
  } finally { globalThis.fetch = saved; }
});
