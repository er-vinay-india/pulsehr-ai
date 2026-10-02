import { DEFAULT_ASSISTANT_IDENTITY } from './identity.js';
import { inferHRIDAYTool, presentHRIDAYAnswer } from './presentation.js';
import { initialHRIDAYActivity, advanceHRIDAYActivity } from './activity.js';

export class HRIDAYConversation {
  constructor(transport) {
    this.transport = transport;
    this.listeners = new Set();
    this.diagnostics = new Map();
    this.sequence = 0;
    this.request = null;
    this.priorContext = null;
    this.state = { identity: DEFAULT_ASSISTANT_IDENTITY, messages: [], draft: '', loading: false, status: '', activity: null, announcement: '' };
  }
  subscribe = listener => { this.listeners.add(listener); return () => this.listeners.delete(listener); };
  getSnapshot = () => this.state;
  publish(patch) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach(listener => listener());
  }
  setIdentity = identity => {
    if (identity?.name) this.publish({ identity });
  };
  setDraft = draft => this.publish({ draft });
  announce = announcement => this.publish({ announcement });
  updateMessage(id, patch, state = {}) {
    this.publish({ ...state, messages: this.state.messages.map(message => message.id === id ? { ...message, ...patch } : message) });
  }
  getDiagnostics = id => this.diagnostics.get(id);

  async send(query = this.state.draft, { scope = {}, tool = inferHRIDAYTool(query), retryId = null } = {}) {
    const text = query.trim();
    if (!text || this.request) return;
    const controller = new AbortController();
    const id = retryId || `hriday-${++this.sequence}`;
    const request = { id, controller, rawAnswer: '', delegates: [], terminal: false, activity: initialHRIDAYActivity(this.state.identity.name) };
    const requestDetails = { query: text, scope: { ...scope }, tool };
    this.request = request;
    const diagnostic = { events: [], result: null, request: requestDetails };
    this.diagnostics.set(id, diagnostic);
    const assistant = { id, role: 'assistant', content: '', phase: 'loading', request: requestDetails, artifacts: [] };
    const messages = retryId
      ? this.state.messages.map(message => message.id === id ? assistant : message)
      : [...this.state.messages, { id: `${id}-user`, role: 'user', content: text }, assistant];
    this.publish({ messages, draft: retryId ? this.state.draft : '', loading: true, status: request.activity.text, activity: request.activity, announcement: request.activity.text });

    const current = () => this.request === request && !controller.signal.aborted && !request.terminal;
    const activityEvent = event => {
      if (!current()) return;
      const next = advanceHRIDAYActivity(request.activity, event, tool);
      if (next === request.activity) return;
      const changedText = next.text !== request.activity.text;
      request.activity = next;
      this.publish({ activity: next, status: next.text, ...(changedText ? { announcement: next.text } : {}) });
    };
    const record = event => {
      if (!current()) return;
      diagnostic.events.push(event);
      if (event.type === 'candidate_answer') activityEvent(event);
    };
    const finishError = error => {
      if (!current()) return;
      diagnostic.error = error;
      request.terminal = true;
      this.request = null;
      this.updateMessage(id, { phase: 'error' }, { loading: false, activity: null, announcement: `${this.state.identity.name} couldn’t finish. Your question is saved.` });
    };
    try {
      await this.transport(text, null, tool, scope.datasetId ?? null, scope.sheetId ?? null, {
        onEvent: record,
        onWarRoomInit: data => { if (current()) { request.delegates = data.delegates || []; activityEvent({ type: 'war_room_init', data }); } },
        onDelegatePerspective: data => { if (current()) { diagnostic.perspectives = { ...diagnostic.perspectives, [data.delegate_id]: data }; activityEvent({ type: 'delegate_perspective', data }); } },
        onDelegateVote: data => { if (current()) { diagnostic.votes = { ...diagnostic.votes, [data.delegate_id]: data }; activityEvent({ type: 'delegate_vote', data }); } },
        onStatus: data => activityEvent({ type: 'status', data }),
        onReset: data => {
          if (!current()) return;
          request.rawAnswer = '';
          activityEvent({ type: 'answer_reset', data });
          this.updateMessage(id, { content: '', phase: 'loading' });
        },
        onToken: token => {
          if (!current()) return;
          if (!request.rawAnswer) activityEvent({ type: 'token', data: { token } });
          request.rawAnswer += token || '';
          const content = presentHRIDAYAnswer(request.rawAnswer, { streaming: true, delegates: request.delegates, assistantName: this.state.identity.name });
          this.updateMessage(id, { content, phase: content ? 'streaming' : 'loading' });
        },
        onDone: data => {
          if (!current()) return;
          diagnostic.result = data;
          if (data.assistant_identity?.name) this.setIdentity(data.assistant_identity);
          if (data.prior_context) this.priorContext = data.prior_context;
          const content = presentHRIDAYAnswer(data.answer || request.rawAnswer, { delegates: request.delegates, assistantName: this.state.identity.name });
          request.terminal = true;
          this.request = null;
          this.updateMessage(id, { content, phase: content ? 'complete' : 'error', artifacts: data.artifacts || [] },
            { loading: false, activity: null, announcement: content ? `${this.state.identity.name}’s response is ready.` : `${this.state.identity.name} couldn’t finish. Your question is saved.` });
        },
        onError: finishError,
      }, controller.signal, this.priorContext, scope.snapshotId ?? null, scope.page ?? null, 60.0);
      if (current()) finishError(new Error('Response ended without a completion event.'));
    } catch (error) { finishError(error); }
  }

  stop = () => {
    const request = this.request;
    if (!request) return;
    request.terminal = true;
    request.controller.abort();
    this.request = null;
    this.updateMessage(request.id, { phase: 'stopped' }, { loading: false, activity: null, announcement: 'Response stopped.' });
  };
  retry = message => this.send(message.request.query, { ...message.request, retryId: message.id });
  newChat = () => {
    this.stop();
    this.priorContext = null;
    this.diagnostics.clear();
    this.publish({ messages: [], draft: '', loading: false, activity: null, status: '', announcement: `New conversation with ${this.state.identity.name}.` });
  };
  feedback = (id, feedback) => this.updateMessage(id, { feedback }, { announcement: feedback === 'helpful' ? 'Marked helpful.' : 'Marked as needing improvement.' });
}
