import { inferHRIDAYTool, presentHRIDAYAnswer, presentHRIDAYStatus } from './presentation.js';

export class HRIDAYConversation {
  constructor(transport) {
    this.transport = transport;
    this.listeners = new Set();
    this.diagnostics = new Map();
    this.sequence = 0;
    this.request = null;
    this.priorContext = null;
    this.state = { messages: [], draft: '', loading: false, status: 'Preparing your answer…', announcement: '' };
  }
  subscribe = listener => { this.listeners.add(listener); return () => this.listeners.delete(listener); };
  getSnapshot = () => this.state;
  publish(patch) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach(listener => listener());
  }
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
    const request = { id, controller, rawAnswer: '', delegates: [], terminal: false };
    const requestDetails = { query: text, scope: { ...scope }, tool };
    this.request = request;
    const diagnostic = { events: [], result: null, request: requestDetails };
    this.diagnostics.set(id, diagnostic);
    const assistant = { id, role: 'assistant', content: '', phase: 'loading', request: requestDetails, artifacts: [] };
    const messages = retryId
      ? this.state.messages.map(message => message.id === id ? assistant : message)
      : [...this.state.messages, { id: `${id}-user`, role: 'user', content: text }, assistant];
    this.publish({ messages, draft: retryId ? this.state.draft : '', loading: true, status: 'Preparing your answer…', announcement: 'HRIDAY is preparing your answer.' });

    const current = () => this.request === request && !controller.signal.aborted && !request.terminal;
    const record = event => { if (current()) diagnostic.events.push(event); };
    const finishError = error => {
      if (!current()) return;
      diagnostic.error = error;
      request.terminal = true;
      this.request = null;
      this.updateMessage(id, { phase: 'error' }, { loading: false, announcement: 'HRIDAY couldn’t finish. Your question is saved.' });
    };
    try {
      await this.transport(text, null, tool, scope.datasetId ?? null, scope.sheetId ?? null, {
        onEvent: record,
        onWarRoomInit: data => { if (current()) request.delegates = data.delegates || []; },
        onDelegatePerspective: data => { if (current()) diagnostic.perspectives = { ...diagnostic.perspectives, [data.delegate_id]: data }; },
        onDelegateVote: data => { if (current()) diagnostic.votes = { ...diagnostic.votes, [data.delegate_id]: data }; },
        onStatus: data => {
          if (!current()) return;
          const status = presentHRIDAYStatus(data);
          this.publish({ status, announcement: status });
        },
        onToken: token => {
          if (!current()) return;
          request.rawAnswer += token || '';
          const content = presentHRIDAYAnswer(request.rawAnswer, { streaming: true, delegates: request.delegates });
          this.updateMessage(id, { content, phase: content ? 'streaming' : 'loading' });
        },
        onDone: data => {
          if (!current()) return;
          diagnostic.result = data;
          if (data.prior_context) this.priorContext = data.prior_context;
          const content = presentHRIDAYAnswer(data.answer || request.rawAnswer, { delegates: request.delegates });
          request.terminal = true;
          this.request = null;
          this.updateMessage(id, { content, phase: content ? 'complete' : 'error', artifacts: data.artifacts || [] },
            { loading: false, announcement: content ? 'HRIDAY’s response is ready.' : 'HRIDAY couldn’t finish. Your question is saved.' });
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
    this.updateMessage(request.id, { phase: 'stopped' }, { loading: false, announcement: 'Response stopped.' });
  };
  retry = message => this.send(message.request.query, { ...message.request, retryId: message.id });
  newChat = () => {
    this.stop();
    this.priorContext = null;
    this.diagnostics.clear();
    this.publish({ messages: [], draft: '', loading: false, announcement: 'New conversation with HRIDAY.' });
  };
  feedback = (id, feedback) => this.updateMessage(id, { feedback }, { announcement: feedback === 'helpful' ? 'Marked helpful.' : 'Marked as needing improvement.' });
}
