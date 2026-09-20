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
  ExternalLink
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { askCopilot, getCopilotSuggestions, getAvailableModels } from '../api/client';
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
  const [suggestions, setSuggestions] = useState([]);
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem('pulsehr_selected_model') || 'llama3.1:8b');
  const messagesEndRef = useRef(null);

  // Sync with prop isOpen
  useEffect(() => {
    if (isOpen !== undefined) {
      setPanelOpen(isOpen);
    }
  }, [isOpen]);

  // Load suggestions and models
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

  // Listen for Escape key to close panel
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && panelOpen) {
        handleClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [panelOpen]);

  // Scroll to bottom of chat
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
    setPanelOpen(false);
    if (onClose) onClose();
    if (onToggle) onToggle(false);
  };

  const handleOpen = () => {
    setPanelOpen(true);
    setMinimized(false);
    if (onToggle) onToggle(true);
  };

  const handleSend = async (queryText, tool = null) => {
    const text = (queryText || input).trim();
    if (!text || loading) return;

    setInput('');
    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await askCopilot(text, selectedModel, tool, activeDatasetId, activeSheetId);
      const botMsg = {
        role: 'assistant',
        content: res.answer,
        citations: res.citations || [],
        artifacts: res.artifacts || [],
        model_used: res.model_used || selectedModel
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ Failed to retrieve analysis: ${err.message}. Ensure Ollama or local LLM is active.`,
          citations: [],
          model_used: selectedModel
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* 1. Persistent Floating Launcher Button (Always visible at bottom-right) */}
      {!panelOpen && (
        <button
          type="button"
          className="global-copilot-launcher"
          onClick={handleOpen}
          aria-label="Open AI Copilot"
          title="Open AI Copilot (Ask questions about your data)"
        >
          <BrainCircuit size={22} className="launcher-icon" />
          <span className="launcher-label">Ask Copilot</span>
          <span className="launcher-pulse" />
        </button>
      )}

      {/* 2. Slide-out Copilot Panel */}
      {panelOpen && (
        <div
          className={`copilot-drawer-panel ${minimized ? 'minimized' : ''}`}
          role="dialog"
          aria-label="AI Analytics Copilot"
        >
          {/* Header */}
          <div className="copilot-drawer-header">
            <div className="copilot-header-brand">
              <div className="copilot-icon-wrap">
                <BrainCircuit size={18} />
              </div>
              <div className="copilot-title-group">
                <div className="copilot-title-row">
                  <h3>AI Copilot</h3>
                  {activeSheetName && (
                    <span className="copilot-context-badge" title={`Context: ${activeSheetName}`}>
                      <FileSpreadsheet size={11} />
                      <span className="context-name">{activeSheetName}</span>
                    </span>
                  )}
                </div>
                <div className="copilot-model-select-row">
                  <Cpu size={12} color="var(--text-muted, #94a3b8)" />
                  <select
                    value={selectedModel}
                    onChange={(e) => handleModelChange(e.target.value)}
                    className="model-dropdown-mini"
                    aria-label="Select Local Model"
                  >
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                    {models.length === 0 && <option value="llama3.1:8b">Default Model (Llama 3.1)</option>}
                  </select>
                </div>
              </div>
            </div>

            {/* Header Controls */}
            <div className="copilot-header-actions">
              <button
                type="button"
                className="header-ctrl-btn"
                onClick={() => setMinimized(!minimized)}
                title={minimized ? 'Expand Copilot' : 'Minimize Copilot'}
                aria-label={minimized ? 'Expand' : 'Minimize'}
              >
                {minimized ? <Maximize2 size={15} /> : <Minimize2 size={15} />}
              </button>
              <button
                type="button"
                className="header-ctrl-btn close"
                onClick={handleClose}
                title="Close Copilot (Esc)"
                aria-label="Close"
              >
                <X size={17} />
              </button>
            </div>
          </div>

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
                    <Sparkles size={13} color="var(--accent, #38bdf8)" />
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
              <div className="copilot-messages-list">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`copilot-msg-bubble ${msg.role}`}>
                    <div className="msg-avatar">
                      {msg.role === 'assistant' ? <Bot size={15} /> : <User size={15} />}
                    </div>
                    <div className="msg-content-wrap">
                      <div className="msg-text markdown-body">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm, remarkMath]}
                          rehypePlugins={[rehypeKatex]}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      </div>

                      {/* Citations & Evidence Links */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="msg-citations-wrap">
                          <span className="citation-title">Supporting Records:</span>
                          <div className="citation-pills-row">
                            {msg.citations.slice(0, 4).map((cit, cIdx) => (
                              <span key={cIdx} className="citation-pill" title={cit.text}>
                                <FileSpreadsheet size={11} />
                                <span>{cit.source || cit.sheet || 'Source Sheet'}</span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {msg.model_used && (
                        <div className="msg-meta-row">
                          <span className="msg-model-tag">{msg.model_used}</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {loading && (
                  <div className="copilot-msg-bubble assistant loading">
                    <div className="msg-avatar">
                      <Bot size={15} />
                    </div>
                    <div className="msg-loading-dots">
                      <span className="dot" />
                      <span className="dot" />
                      <span className="dot" />
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input Form */}
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
                  placeholder="Ask a question about your sheets..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={loading}
                />
                <button
                  type="submit"
                  className="copilot-send-btn"
                  disabled={!input.trim() || loading}
                  aria-label="Send query"
                >
                  <Send size={16} />
                </button>
              </form>
            </div>
          )}
        </div>
      )}
    </>
  );
}
