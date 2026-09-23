import React, { useEffect, useState, useRef } from "react";
import {
  Send,
  Sparkles,
  BrainCircuit,
  Bot,
  User,
  FileSpreadsheet,
  Cpu,
  Clock,
  RotateCcw,
  Square,
  Zap,
  CheckCircle2,
  AlertTriangle
} from "lucide-react";
import MarkdownView from "../components/MarkdownView";
import { askCopilot, streamCopilotQuery, getCopilotSuggestions, getAvailableModels } from "../api/client";
import CopilotTools from "../components/CopilotTools";

export default function CopilotPage({ onSelectEmployee }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Hello! Ask me about your **uploaded sheets** and the records that connect them.\n\nUse **Calculate from data** for exact totals and comparisons, or **Create sheet PowerPoint** to prepare a report.",
      citations: [],
      model_used: "System"
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState("Preparing your answer…");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [lastQuery, setLastQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem("pulsehr_selected_model") || "phi4-mini:latest");

  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);
  const timerIntervalRef = useRef(null);

  useEffect(() => {
    getCopilotSuggestions().then(res => setSuggestions(res.suggestions || [])).catch(() => {});
    getAvailableModels().then(res => {
      const avail = res.models || [];
      setModels(avail);
      if (avail.length > 0) {
        const saved = localStorage.getItem("pulsehr_selected_model");
        const match = avail.find(m => m.id === saved) || avail[0];
        setSelectedModel(match.id);
      }
    }).catch(() => {});
  }, []);

  // Timer & progressive status updates during loading
  useEffect(() => {
    if (loading) {
      setElapsedSeconds(0);
      setLoadingStatus("Preparing your answer…");
      timerIntervalRef.current = setInterval(() => {
        setElapsedSeconds(prev => {
          const next = prev + 1;
          if (next === 2) {
            setLoadingStatus("Connecting to local engine and analyzing context…");
          } else if (next === 5) {
            setLoadingStatus(`Streaming response from ${selectedModel}…`);
          } else if (next === 12) {
            setLoadingStatus("Synthesizing metrics and citations (still computing)…");
          } else if (next === 25) {
            setLoadingStatus("Generating detailed findings with local engine…");
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

  useEffect(() => {
    if (messages.length > 1) {
      messagesEndRef.current?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"
      });
    }
  }, [messages, loading]);

  const handleModelChange = (modelId) => {
    setSelectedModel(modelId);
    localStorage.setItem("pulsehr_selected_model", modelId);
  };

  const handleStopWaiting = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setLoading(false);
    setMessages(prev => [
      ...prev,
      {
        role: "assistant",
        content: "_Response stopped by user. (Client connection closed; background inference may finish or terminate.)_",
        citations: [],
        model_used: selectedModel,
        isCancelled: true
      }
    ]);
  };

  const handleSend = async (queryText, tool = null) => {
    const text = (queryText || input).trim();
    if (!text || loading) return;

    setInput("");
    setLastQuery(text);
    const userMsg = { role: "user", content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let streamAnswer = "";

    try {
      await streamCopilotQuery(
        text,
        selectedModel,
        tool,
        null,
        null,
        {
          onStatus: (st) => {
            if (st.message) {
              setLoadingStatus(st.message);
            }
          },
          onToken: (token) => {
            streamAnswer += token;
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              if (last && last.role === "assistant" && last.isStreaming) {
                last.content = streamAnswer;
              } else {
                updated.push({
                  role: "assistant",
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
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              const finalContent = doneData.answer || streamAnswer;
              const completedMsg = {
                role: "assistant",
                content: finalContent,
                citations: doneData.citations || [],
                artifacts: doneData.artifacts || [],
                model_used: doneData.model_used || selectedModel,
                timings: doneData.timings || null,
                isStreaming: false
              };
              if (last && last.role === "assistant" && last.isStreaming) {
                updated[updated.length - 1] = completedMsg;
              } else {
                updated.push(completedMsg);
              }
              return updated;
            });
          },
          onError: async (streamErr) => {
            if (controller.signal.aborted) return;
            // Fallback to standard request
            try {
              const res = await askCopilot(text, selectedModel, tool, null, null, controller.signal);
              setMessages(prev => [
                ...prev.filter(m => !m.isStreaming),
                {
                  role: "assistant",
                  content: res.answer,
                  citations: res.citations || [],
                  artifacts: res.artifacts || [],
                  model_used: res.model_used || selectedModel,
                  timings: res.timings || null
                }
              ]);
            } catch (fallbackErr) {
              if (controller.signal.aborted) return;
              setMessages(prev => [
                ...prev.filter(m => !m.isStreaming),
                {
                  role: "assistant",
                  content: `⚠️ Failed to retrieve analysis: ${fallbackErr.message || streamErr.message}. Ensure Ollama or local engine is running.`,
                  citations: [],
                  model_used: selectedModel,
                  isError: true
                }
              ]);
            }
          }
        },
        controller.signal
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setMessages(prev => [
          ...prev.filter(m => !m.isStreaming),
          {
            role: "assistant",
            content: `⚠️ Failed to retrieve analysis: ${err.message}. Ensure Ollama or local engine is running.`,
            citations: [],
            model_used: selectedModel,
            isError: true
          }
        ]);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
      setLoading(false);
    }
  };

  const handleRetry = () => {
    if (lastQuery) {
      handleSend(lastQuery);
    }
  };

  const activeModelMeta = models.find(m => m.id === selectedModel);

  return (
    <div className="copilot-page">
      {/* Header Banner */}
      <div className="copilot-header">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <div className="brand-badge">
              <BrainCircuit size={18} color="var(--brand-400)" />
              <span>Your workspace assistant</span>
            </div>
            <h2>HR Copilot</h2>
            <p className="subtitle">
              Ask questions, calculate metrics, and turn your sheets into reports.
            </p>
          </div>

          {/* Model Selector Dropdown & Speed Tag */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "0.6rem",
            background: "#1c1815",
            border: "1px solid var(--border-strong, #473f38)",
            borderRadius: "var(--radius-sm)",
            padding: "0.5rem 0.85rem",
            maxWidth: "100%"
          }}>
            <Cpu size={16} color="var(--brand-400)" style={{ flexShrink: 0 }} />
            <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--fg-secondary, #d7c5b5)", textTransform: "uppercase", whiteSpace: "nowrap" }}>
              Active Model:
            </span>
            <select
              aria-label="Active AI model"
              value={selectedModel}
              onChange={e => handleModelChange(e.target.value)}
              style={{
                background: "none",
                border: "none",
                color: "#ffffff",
                fontWeight: 700,
                fontSize: "0.85rem",
                outline: "none",
                cursor: "pointer",
                maxWidth: "240px",
                textOverflow: "ellipsis"
              }}
            >
              {models.map(m => (
                <option key={m.id} value={m.id} style={{ background: "#1c1815", color: "#fff9f2" }}>
                  {m.name} ({m.speed || "standard"})
                </option>
              ))}
            </select>
            {activeModelMeta?.speed && (
              <span
                className={`model-speed-tag speed-${activeModelMeta.speed}`}
                style={{
                  fontSize: "0.65rem",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  padding: "2px 6px",
                  borderRadius: "4px",
                  border: "1px solid currentColor"
                }}
              >
                {activeModelMeta.speed}
              </span>
            )}
          </div>
        </div>

        {/* Multi-Source Grounding Indicator */}
        <div style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.5rem",
          background: "rgba(126, 231, 217, 0.08)",
          border: "1px solid rgba(126, 231, 217, 0.25)",
          padding: "0.25rem 0.75rem",
          borderRadius: "var(--radius-full)",
          fontSize: "0.75rem",
          color: "var(--accent-500)",
          marginTop: "0.75rem"
        }}>
          <FileSpreadsheet size={13} />
          <span>Source grounding: uploaded sheets and related records</span>
        </div>
      </div>

      {/* Suggested Prompt Chips */}
      <div className="suggestions-container">
        <div className="suggestions-label">
          <Sparkles size={14} color="var(--brand-400)" />
          <span>Start with a question:</span>
        </div>
        <div className="chips-row">
          {suggestions.map((s, idx) => (
            <button
              key={idx}
              type="button"
              className="chip-btn"
              onClick={() => handleSend(s)}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <CopilotTools loading={loading} onRun={handleSend} />

      {/* Messages Thread */}
      <div className="chat-thread" aria-live="polite">
        {messages.map((m, idx) => (
          <div key={idx} className={`chat-message ${m.role}`}>
            <div className="avatar-icon">
              {m.role === "assistant" ? <Bot size={18} /> : <User size={18} />}
            </div>
            <div className="message-content">
              <div className="message-bubble">
                <MarkdownView content={m.content} />
                {m.citations?.length > 0 && (
                  <details style={{ marginTop: 12 }}>
                    <summary style={{ cursor: "pointer", fontWeight: 600, color: "var(--fg-secondary)" }}>
                      Source records ({m.citations.length})
                    </summary>
                    {m.citations.map(c => (
                      <div key={c.chunk_id} style={{ margin: "8px 0", padding: "8px 12px", background: "rgba(255,255,255,0.03)", borderRadius: 6 }}>
                        <strong>{c.source_file} / {c.sheet_name}</strong>
                        {c.type === "exact_join" && <span> · Connected by exact key</span>}
                        <p style={{ margin: "4px 0 0 0", fontSize: "0.8rem", color: "var(--fg-muted)" }}>{c.text}</p>
                      </div>
                    ))}
                  </details>
                )}
                {m.artifacts?.map(artifact => (
                  <a key={artifact.url} href={artifact.url} download className="chip-btn" style={{ display: "inline-block", marginTop: 12 }}>
                    Download PowerPoint
                  </a>
                ))}
                {m.role === "assistant" && (
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: "0.5rem",
                    fontSize: "0.72rem",
                    color: "var(--fg-secondary, #d7c5b5)",
                    marginTop: "0.6rem",
                    borderTop: "1px solid var(--border-subtle)",
                    paddingTop: "0.4rem"
                  }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                      <Cpu size={12} color="var(--brand-400)" />
                      Answered by: <strong>{m.model_used || selectedModel}</strong>
                    </span>
                    {m.timings && (
                      <span className="msg-timing-tag" title={`Prompt eval: ${m.timings.context_ms}ms, LLM: ${m.timings.llm_ms}ms`}>
                        <Clock size={11} /> {m.timings.total_ms}ms
                      </span>
                    )}
                    {m.isError && lastQuery && (
                      <button
                        type="button"
                        onClick={handleRetry}
                        className="msg-retry-inline-btn"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          background: "rgba(244,63,94,0.15)",
                          border: "1px solid rgba(244,63,94,0.3)",
                          color: "#f87171",
                          padding: "2px 8px",
                          borderRadius: 4,
                          cursor: "pointer",
                          fontSize: "0.72rem"
                        }}
                      >
                        <RotateCcw size={11} /> Retry query
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Visible Progressive Loading Feedback Card */}
        {loading && (
          <div className="chat-message assistant" role="status" aria-live="polite">
            <div className="avatar-icon"><Bot size={18} /></div>
            <div className="message-content">
              <div className="copilot-waiting-card">
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, width: "100%" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div className="copilot-loading-spinner" aria-hidden="true" />
                    <div>
                      <div className="waiting-status-lead" style={{ fontWeight: 700, fontSize: "0.85rem", color: "#f8fafc" }}>
                        Generating answer
                      </div>
                      <div className="waiting-status-text" style={{ fontSize: "0.76rem", color: "#94a3b8", marginTop: 2 }}>
                        {loadingStatus}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="waiting-timer-badge" aria-label={`Elapsed time: ${elapsedSeconds} seconds`}>
                      <Clock size={11} /> {elapsedSeconds}s
                    </span>
                    <button
                      type="button"
                      onClick={handleStopWaiting}
                      className="copilot-stop-wait-btn"
                      aria-label="Stop waiting for response"
                    >
                      <Square size={10} fill="currentColor" /> Stop
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="chat-input-bar">
        <form onSubmit={e => { e.preventDefault(); handleSend(); }}>
          <input
            type="text"
            aria-label="Message the HR copilot"
            placeholder={`Ask ${selectedModel} anything about attendance, ratings, or uploaded files...`}
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={loading}
          />
          <button type="submit" aria-label="Send message" className="btn-primary" disabled={loading || !input.trim()}>
            <Send size={16} />
            <span>Send</span>
          </button>
        </form>
      </div>
    </div>
  );
}
