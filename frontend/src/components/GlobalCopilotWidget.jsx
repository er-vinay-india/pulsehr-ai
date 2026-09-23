import React, { useEffect, useState, useRef } from 'react';
import {
  BrainCircuit,
  X,
  Send,
  Sparkles,
  Minimize2,
  Maximize2,
  FileSpreadsheet,
  Cpu,
  Bot,
  User,
  RefreshCw,
  Square,
  AlertCircle,
  Clock
} from 'lucide-react';
import MarkdownView from './MarkdownView';
import { askCopilot, streamCopilotQuery, getCopilotSuggestions, getAvailableModels } from '../api/client';
import CopilotTools from './CopilotTools';

export default function GlobalCopilotWidget({
  isOpen = false,
  onToggle,
  onClose,
  activeDatasetId = null,
  activeSheetId = null,
  activeSheetName = '',
  onSelectEmployee
}) {
  const [panelOpen, setPanelOpen] = useState(isOpen);
  const [minimized, setMinimized] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! Ask me about your **uploaded spreadsheets**, calculations, or cross-sheet relationships.\n\nUse **Calculate from data** for exact totals, or **Create sheet PowerPoint** for presentations.',
      citations: [],
      model_used: 'System'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('Preparing your answer…');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [lastQuery, setLastQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem('pulsehr_selected_model') || 'phi4-mini:latest');
  
  const messagesEndRef = useRef(null);
  const launcherRef = useRef(null);
  const abortControllerRef = useRef(null);
  const timerIntervalRef = useRef(null);

  // Sync with prop isOpen
  useEffect(() => {
    if (isOpen !== undefined) {
      setPanelOpen(isOpen);
    }
  }, [isOpen]);

  // Load suggestions and available local models
  useEffect(() => {
    getCopilotSuggestions().then((res) => setSuggestions(res.suggestions || [])).catch(() => {});
    getAvailableModels().then((res) => {
      const avail = res.models || [];
      setModels(avail);
      if (avail.length > 0) {
        const saved = localStorage.getItem('pulsehr_selected_model');
        const match = avail.find((m) => m.id === saved) || avail[0];
        setSelectedModel(match.id);
      }
    }).catch(() => {});
  }, []);

  // Listen for Escape key to close panel with focus restoration
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && panelOpen) {
        handleClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [panelOpen]);

  // Elapsed timer during loading
  useEffect(() => {
    if (loading) {
      setElapsedSeconds(0);
      setLoadingStatus('Preparing your answer…');
      timerIntervalRef.current = setInterval(() => {
        setElapsedSeconds((prev) => {
          const next = prev + 1;
          if (next === 4) {
            setLoadingStatus('Searching uploaded sheets & related records…');
          } else if (next === 11) {
            setLoadingStatus(`Consulting local model (${selectedModel})…`);
          } else if (next === 25) {
            setLoadingStatus('Generating detailed response with local engine (still running)…');
          }
          return next;
        });
      }, 1000);
    } else {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
    }
    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    };
  }, [loading, selectedModel]);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    if (messages.length > 1 && panelOpen && !minimized) {
      messagesEndRef.current?.scrollIntoView({
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
      });
    }
  }, [messages, loading, panelOpen, minimized]);

  const handleModelChange = (modelId) => {
    setSelectedModel(modelId);
    localStorage.setItem('pulsehr_selected_model', modelId);
  };

  const handleClose = () => {
    // Abort pending request if active
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setLoading(false);
    setPanelOpen(false);
    if (onClose) onClose();
    if (onToggle) onToggle(false);
    // Restore focus to launcher button
    setTimeout(() => {
      launcherRef.current?.focus();
    }, 50);
  };

  const handleOpen = () => {
    setPanelOpen(true);
    setMinimized(false);
    if (onToggle) onToggle(true);
  };

  const handleStopWaiting = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setLoading(false);
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        content: '_Response stopped by user. (Client connection closed; background inference may finish or terminate.)_',
        citations: [],
        model_used: selectedModel,
        isCancelled: true
      }
    ]);
  };

  const handleSend = async (queryText, tool = null) => {
    const text = (queryText || input).trim();
    if (!text || loading) return;

    setInput('');
    setLastQuery(text);
    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Placeholder message for streaming tokens
    let streamAnswer = '';
    const tempAssistantIndex = messages.length + 1;

    try {
      // Attempt SSE streaming for immediate token-by-token feedback
      await streamCopilotQuery(
        text,
        selectedModel,
        tool,
        activeDatasetId,
        activeSheetId,
        {
          onStatus: (st) => {
            if (st.message) {
              setLoadingStatus(st.message);
            }
          },
          onToken: (token) => {
            streamAnswer += token;
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last && last.role === 'assistant' && last.isStreaming) {
                last.content = streamAnswer;
              } else {
                updated.push({
                  role: 'assistant',
                  content: streamAnswer,
                  citations: [],
                  model_used: selectedModel,
                  isStreaming: true
                });
              }
              return updated;
            });
          },
          onDone: (doneData) => {
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              const finalContent = doneData.answer || streamAnswer;
              const completedMsg = {
                role: 'assistant',
                content: finalContent,
                citations: doneData.citations || [],
                artifacts: doneData.artifacts || [],
                model_used: doneData.model_used || selectedModel,
                timings: doneData.timings || null,
                isStreaming: false
              };
              if (last && last.role === 'assistant' && last.isStreaming) {
                updated[updated.length - 1] = completedMsg;
              } else {
                updated.push(completedMsg);
              }
              return updated;
            });
          },
          onError: async (streamErr) => {
            // If streaming was aborted by user, ignore
            if (controller.signal.aborted) return;
            // Fallback to standard non-streaming query
            try {
              const res = await askCopilot(text, selectedModel, tool, activeDatasetId, activeSheetId, controller.signal);
              setMessages((prev) => [
                ...prev.filter((m) => !m.isStreaming),
                {
                  role: 'assistant',
                  content: res.answer,
                  citations: res.citations || [],
                  artifacts: res.artifacts || [],
                  model_used: res.model_used || selectedModel,
                  timings: res.timings || null
                }
              ]);
            } catch (fallbackErr) {
              if (controller.signal.aborted) return;
              setMessages((prev) => [
                ...prev.filter((m) => !m.isStreaming),
                {
                  role: 'assistant',
                  content: `⚠️ Failed to retrieve analysis: ${fallbackErr.message}. Ensure Ollama or local LLM is active.`,
                  citations: [],
                  model_used: selectedModel,
                  isError: true,
                  failedQuery: text
                }
              ]);
            }
          }
        },
        controller.signal
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setMessages((prev) => [
          ...prev.filter((m) => !m.isStreaming),
          {
            role: 'assistant',
            content: `⚠️ Failed to retrieve analysis: ${err.message}. Ensure Ollama or local LLM is active.`,
            citations: [],
            model_used: selectedModel,
            isError: true,
            failedQuery: text
          }
        ]);
      }
    } finally {
      abortControllerRef.current = null;
      setLoading(false);
    }
  };

  return (
    <>
      {/* 1. Persistent Floating Launcher Button */}
      {!panelOpen && (
        <button
          ref={launcherRef}
          type="button"
          className="global-copilot-launcher"
          onClick={handleOpen}
          aria-label="Open AI Analytics Copilot"
          title="Open AI Copilot (Ask questions about your data)"
          aria-expanded={false}
          aria-controls="copilot-drawer-panel"
        >
          <BrainCircuit size={22} className="launcher-icon" aria-hidden="true" />
          <span className="launcher-label">Ask Copilot</span>
          <span className="launcher-pulse" aria-hidden="true" />
        </button>
      )}

      {/* 2. Slide-out Copilot Panel */}
      {panelOpen && (
        <aside
          id="copilot-drawer-panel"
          className={`copilot-drawer-panel ${minimized ? 'minimized' : ''}`}
          role="dialog"
          aria-label="AI Analytics Copilot"
          aria-modal={!minimized}
        >
          {/* Header with robust flex-shrink rules preventing close button clipping */}
          <header className="copilot-drawer-header">
            <div className="copilot-header-brand">
              <div className="copilot-icon-wrap" aria-hidden="true">
                <BrainCircuit size={18} />
              </div>
              <div className="copilot-title-group">
                <div className="copilot-title-row">
                  <h3>AI Copilot</h3>
                  {activeSheetName && (
                    <span className="copilot-context-badge" title={`Context: ${activeSheetName}`}>
                      <FileSpreadsheet size={11} aria-hidden="true" />
                      <span className="context-name">{activeSheetName}</span>
                    </span>
                  )}
                </div>
                <div className="copilot-model-select-row">
                  <Cpu size={12} color="var(--fg-secondary, #d4c8bd)" aria-hidden="true" />
                  <select
                    value={selectedModel}
                    onChange={(e) => handleModelChange(e.target.value)}
                    className="model-dropdown-mini"
                    aria-label="Active Model"
                    title={`Model: ${selectedModel}`}
                  >
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                    {models.length === 0 && <option value="phi4-mini:latest">Phi-4 Mini (3.8B) · Fast</option>}
                  </select>
                </div>
              </div>
            </div>

            {/* Header Controls: Guaranteed flex-shrink: 0 and high-contrast accessible buttons */}
            <div className="copilot-header-actions">
              <button
                type="button"
                className="header-ctrl-btn"
                onClick={() => setMinimized(!minimized)}
                title={minimized ? 'Expand Copilot' : 'Minimize Copilot'}
                aria-label={minimized ? 'Expand Copilot' : 'Minimize Copilot'}
              >
                {minimized ? <Maximize2 size={16} aria-hidden="true" /> : <Minimize2 size={16} aria-hidden="true" />}
              </button>
              <button
                type="button"
                className="header-ctrl-btn close"
                onClick={handleClose}
                title="Close Copilot (Esc)"
                aria-label="Close Copilot (Esc)"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>
          </header>

          {/* Body (Hidden when minimized) */}
          {!minimized && (
            <div className="copilot-drawer-body">
              {/* Tools Strip */}
              <div className="copilot-tools-container">
                <CopilotTools loading={loading} onRun={handleSend} />
              </div>

              {/* Suggestions Chips */}
              {suggestions.length > 0 && messages.length <= 2 && (
                <div className="copilot-suggestions-strip">
                  <div className="suggestions-label">
                    <Sparkles size={13} color="var(--accent-500, #38bdf8)" aria-hidden="true" />
                    <span>Suggested Questions:</span>
                  </div>
                  <div className="suggestions-chips-row">
                    {suggestions.map((s, idx) => (
                      <button
                        key={idx}
                        type="button"
                        className="suggestion-chip"
                        onClick={() => handleSend(s)}
                        disabled={loading}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Chat Message History */}
              <div
                className="copilot-messages-list"
                role="log"
                aria-live="polite"
                aria-label="Copilot conversation messages"
              >
                {messages.map((msg, idx) => (
                  <div key={idx} className={`copilot-msg-bubble ${msg.role}`}>
                    <div className="msg-avatar" aria-hidden="true">
                      {msg.role === 'assistant' ? <Bot size={15} /> : <User size={15} />}
                    </div>
                    <div className="msg-content-wrap">
                      <div className="msg-text markdown-body">
                        <MarkdownView content={msg.content} />
                      </div>

                      {/* Supporting Citations */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="msg-citations-wrap">
                          <span className="citation-title">Supporting Records:</span>
                          <div className="citation-pills-row">
                            {msg.citations.slice(0, 4).map((cit, cIdx) => (
                              <span key={cIdx} className="citation-pill" title={cit.text || JSON.stringify(cit)}>
                                <FileSpreadsheet size={11} aria-hidden="true" />
                                <span>{cit.source || cit.sheet || 'Source Sheet'}</span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Model & Timings Meta Tag */}
                      <div className="msg-meta-row">
                        {msg.model_used && <span className="msg-model-tag">{msg.model_used}</span>}
                        {msg.timings?.total_ms && (
                          <span className="msg-timing-tag" title="Execution latency">
                            <Clock size={10} aria-hidden="true" />
                            {msg.timings.total_ms > 1000
                              ? `${(msg.timings.total_ms / 1000).toFixed(1)}s`
                              : `${Math.round(msg.timings.total_ms)}ms`}
                          </span>
                        )}
                        {msg.isError && msg.failedQuery && (
                          <button
                            type="button"
                            className="msg-retry-inline-btn"
                            onClick={() => handleSend(msg.failedQuery)}
                            title="Retry query"
                          >
                            <RefreshCw size={11} aria-hidden="true" /> Retry
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}

                {/* Visible, Accessible Loading State with Elapsed Timer & Stop Waiting */}
                {loading && (
                  <div
                    className="copilot-msg-bubble assistant loading"
                    role="status"
                    aria-live="polite"
                    aria-label={`Copilot is answering: ${loadingStatus} (${elapsedSeconds}s elapsed)`}
                  >
                    <div className="msg-avatar" aria-hidden="true">
                      <Bot size={15} />
                    </div>
                    <div className="copilot-waiting-card">
                      <div className="waiting-status-row">
                        <div className="copilot-loading-spinner" aria-hidden="true" />
                        <span className="waiting-status-text">{loadingStatus}</span>
                        <span className="waiting-timer-badge">
                          <Clock size={11} aria-hidden="true" /> {elapsedSeconds}s
                        </span>
                      </div>
                      <div className="waiting-actions-row">
                        <span className="waiting-explainer">
                          {elapsedSeconds < 8
                            ? 'Evaluating query and checking deterministic tools…'
                            : elapsedSeconds < 20
                            ? 'Reading spreadsheet records and generating factual answer…'
                            : 'Complex inference in progress on local engine…'}
                        </span>
                        <button
                          type="button"
                          className="copilot-stop-wait-btn"
                          onClick={handleStopWaiting}
                          title="Stop waiting for this response"
                          aria-label="Stop waiting for response"
                        >
                          <Square size={11} aria-hidden="true" /> Stop waiting
                        </button>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input Form Pinned to Bottom */}
              <form
                className="copilot-input-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSend();
                }}
              >
                <input
                  type="text"
                  className="copilot-text-input"
                  placeholder="Ask a question about your sheets…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={loading}
                  aria-label="Query input"
                />
                <button
                  type="submit"
                  className="copilot-send-btn"
                  disabled={!input.trim() || loading}
                  aria-label="Send query"
                  title="Send query"
                >
                  <Send size={16} aria-hidden="true" />
                </button>
              </form>
            </div>
          )}
        </aside>
      )}
    </>
  );
}
