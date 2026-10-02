import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ArrowUp, ArrowDown, Square, SquarePen, X, Maximize2, Minimize2, Copy, ThumbsUp, ThumbsDown, RefreshCw, Download } from 'lucide-react';
import AnimatedAcousticOrb from '../presentation/AnimatedAcousticOrb.jsx';
import MarkdownView from '../MarkdownView.jsx';
import { useHRIDAY } from './HRIDAYProvider.jsx';
import { presentArtifacts } from './presentation.js';
import IconButton from './IconButton.jsx';

export default function HRIDAYChat({ scope = {}, onClose, expanded = false, onExpand, inputRef, mobile = false, fullPage = false }) {
  const { conversation, messages, draft, loading, status, announcement } = useHRIDAY();
  const localInput = useRef(null);
  const textarea = inputRef || localInput;
  const transcript = useRef(null);
  const nearLatest = useRef(true);
  const [showLatest, setShowLatest] = useState(false);

  useLayoutEffect(() => {
    const element = textarea.current;
    if (!element) return;
    element.style.height = 'auto';
    element.style.height = `${Math.min(element.scrollHeight, 144)}px`;
  }, [draft, textarea]);
  useLayoutEffect(() => {
    const element = transcript.current;
    if (!element) return;
    if (nearLatest.current) element.scrollTop = element.scrollHeight;
    else setShowLatest(true);
  }, [messages]);
  useEffect(() => {
    if (!messages.length) { nearLatest.current = true; setShowLatest(false); }
  }, [messages.length]);

  const send = () => {
    if (loading || !draft.trim()) return;
    nearLatest.current = true;
    setShowLatest(false);
    conversation.send(undefined, { scope: typeof scope === 'function' ? scope() : scope });
  };
  const newChat = () => {
    if (draft.trim() && !window.confirm('Start a new conversation and discard your unsent draft?')) return;
    conversation.newChat();
    textarea.current?.focus();
  };
  const copy = async message => {
    try { await navigator.clipboard.writeText(message.content); conversation.announce('Response copied.'); }
    catch { conversation.announce('Copy is unavailable. You can select and copy the response text.'); }
  };
  return <div className={`hriday-chat${fullPage ? ' hriday-chat--page' : ''}`}>
    <header className="hriday-chat-header">
      <div className="hriday-identity"><span className="hriday-original-heart" aria-hidden="true"><AnimatedAcousticOrb compact /></span><h2>HRIDAY</h2></div>
      <div className="hriday-header-actions">
        <IconButton label="New conversation" onClick={newChat}><SquarePen size={18} aria-hidden="true" /></IconButton>
        {onExpand && !mobile && <IconButton label={expanded ? 'Compact chat' : 'Expand chat'} onClick={onExpand}>
          {expanded ? <Minimize2 size={18} aria-hidden="true" /> : <Maximize2 size={18} aria-hidden="true" />}
        </IconButton>}
        {onClose && <IconButton label="Close HRIDAY" onClick={onClose}><X size={20} aria-hidden="true" /></IconButton>}
      </div>
    </header>
    <div ref={transcript} className="hriday-transcript" role="log" tabIndex={0} aria-label="Conversation with HRIDAY" aria-live="off"
      onScroll={event => {
        const element = event.currentTarget;
        nearLatest.current = element.scrollHeight - element.clientHeight - element.scrollTop < 80;
        if (nearLatest.current) setShowLatest(false);
      }}>
      {!messages.length && <div className="hriday-welcome"><h3>How can I help?</h3><p>Ask a question, explore an idea, or tell me what you need.</p></div>}
      {messages.map(message => <article key={message.id} className={`hriday-message hriday-message--${message.role}`} aria-label={message.role === 'user' ? 'You' : 'HRIDAY'}>
        <div className="hriday-message-author">{message.role === 'user' ? 'You' : 'HRIDAY'}</div>
        {message.role === 'user' ? <div className="hriday-user-bubble">{message.content}</div> : <>
          {message.content && <MarkdownView content={message.content} className="hriday-answer" />}
          {message.phase === 'loading' && <div className="hriday-working"><span aria-hidden="true" className="hriday-status-dot" />{status}</div>}
          {message.phase === 'stopped' && <p className="hriday-recovery">{message.content ? 'Response stopped. This answer is incomplete.' : 'Stopped. You can ask again or change your question.'}</p>}
          {message.phase === 'error' && <div className="hriday-recovery">
            <p>{message.content ? 'This answer is incomplete. I couldn’t finish it. Your question is saved.' : 'I couldn’t finish that. Your question is saved.'}</p>
            <IconButton label="Try again" onClick={() => conversation.retry(message)} disabled={loading}><RefreshCw size={18} aria-hidden="true" /></IconButton>
          </div>}
          {message.phase === 'complete' && <>
            {presentArtifacts(message.artifacts).map((artifact, index) => <a className="hriday-artifact" key={`${artifact.url}-${index}`} href={artifact.url} download>
              <Download size={16} aria-hidden="true" /><span>{artifact.name || 'Download presentation'}</span>
            </a>)}
            <div className="hriday-answer-actions">
              <IconButton label="Copy response" onClick={() => copy(message)}><Copy size={16} aria-hidden="true" /></IconButton>
              <IconButton label="Helpful" aria-pressed={message.feedback === 'helpful'} onClick={() => conversation.feedback(message.id, 'helpful')}><ThumbsUp size={16} aria-hidden="true" /></IconButton>
              <IconButton label="Needs improvement" aria-pressed={message.feedback === 'needs-work'} onClick={() => conversation.feedback(message.id, 'needs-work')}><ThumbsDown size={16} aria-hidden="true" /></IconButton>
            </div>
          </>}
        </>}
      </article>)}
    </div>
    {showLatest && <button type="button" className="hriday-jump-latest" onClick={() => {
      nearLatest.current = true; transcript.current.scrollTop = transcript.current.scrollHeight; setShowLatest(false);
    }}><ArrowDown size={16} aria-hidden="true" />Jump to latest</button>}
    <form className="hriday-composer" onSubmit={event => { event.preventDefault(); send(); }}>
      <div className="hriday-input-row">
        <textarea ref={textarea} rows={1} value={draft} aria-label="Message HRIDAY" placeholder="Ask HRIDAY…"
          onChange={event => conversation.setDraft(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && !event.isComposing && !loading && !mobile
              && window.matchMedia('(pointer: fine)').matches) { event.preventDefault(); send(); }
          }} />
        <IconButton label={loading ? 'Stop response' : 'Send message'} className="hriday-composer-action" disabled={!loading && !draft.trim()}
          onClick={loading ? conversation.stop : send}>
          {loading ? <Square size={17} aria-hidden="true" /> : <ArrowUp size={20} aria-hidden="true" />}
        </IconButton>
      </div>
    </form>
    <div className="hriday-sr-only" role="status" aria-live="polite" aria-atomic="true">{announcement}</div>
  </div>;
}
