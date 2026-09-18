import React, { useEffect, useState, useRef } from "react";
import { Send, Sparkles, BrainCircuit, Bot, User, Bookmark, FileSpreadsheet, CheckCircle2 } from "lucide-react";
import { askCopilot, getCopilotSuggestions } from "../api/client";

export default function CopilotPage({ onSelectEmployee }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Hello! I am **PulseHR AI**, your workforce analytics & tabular intelligence assistant.\n\nI am actively grounded in both your **Kaggle Baseline Attendance Logs** and all **User-Uploaded Spreadsheets** (e.g. `employee_absent_data.csv`, `employee_performance_data.csv`).\n\nYou can ask about overall trends, specific employee records, or inquire directly about data in your uploaded files!",
      citations: []
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    getCopilotSuggestions().then(res => setSuggestions(res.suggestions || []));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (queryText) => {
    const text = (queryText || input).trim();
    if (!text || loading) return;

    setInput("");
    const userMsg = { role: "user", content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await askCopilot(text);
      const botMsg = {
        role: "assistant",
        content: res.answer,
        citations: res.citations || []
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ Failed to retrieve analysis: ${err.message}. Ensure Ollama or local engine is running.`,
          citations: []
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="copilot-page">
      {/* Header Banner */}
      <div className="copilot-header">
        <div className="brand-badge">
          <BrainCircuit size={18} color="var(--brand-400)" />
          <span>Local Ollama Qwen2.5 + nomic-embed-text RAG</span>
        </div>
        <h2>Workforce AI Copilot & Anomaly Reasoning</h2>
        <p className="subtitle">
          Query raw attendance timestamps, department aggregates, and performance correlations in natural language.
        </p>

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
          marginTop: "0.5rem"
        }}>
          <FileSpreadsheet size={13} />
          <span>Multi-Source Grounded: Baseline + Uploaded Sheets Synced</span>
        </div>
      </div>

      {/* Suggested Prompt Chips */}
      <div className="suggestions-container">
        <div className="suggestions-label">
          <Sparkles size={14} color="var(--brand-400)" />
          <span>Suggested Inquiries (Including Uploaded Files):</span>
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

      {/* Messages Thread */}
      <div className="chat-thread">
        {messages.map((m, idx) => (
          <div key={idx} className={`chat-message ${m.role}`}>
            <div className="avatar-icon">
              {m.role === "assistant" ? <Bot size={18} /> : <User size={18} />}
            </div>
            <div className="message-content">
              <div className="message-bubble">
                <div style={{ whiteSpace: "pre-line" }}>{m.content}</div>
              </div>

              {/* Citations / Semantic Grounding */}
              {m.citations && m.citations.length > 0 && (
                <div className="citations-tray">
                  <div className="citations-header">
                    <Bookmark size={13} />
                    <span>Vector Retrieved Records & Sources ({m.citations.length})</span>
                  </div>
                  <div className="citations-list">
                    {m.citations.map((cit, cIdx) => (
                      <div
                        key={cIdx}
                        className="citation-card"
                        onClick={() => cit.metadata?.employee_id !== undefined && onSelectEmployee(cit.metadata.employee_id)}
                      >
                        <div className="citation-top">
                          <span className="cit-name">{cit.metadata?.name || cit.metadata?.employee_name || cit.sheet_name}</span>
                          <span className="cit-score">Relevance: {(cit.relevance_score * 100).toFixed(0)}%</span>
                        </div>
                        <p className="cit-text">{cit.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="chat-message assistant">
            <div className="avatar-icon"><Bot size={18} /></div>
            <div className="message-content">
              <div className="message-bubble loading-bubble">
                <span className="dot-pulse" /> PulseHR AI is reasoning over uploaded sheets and vector tables...
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
            placeholder="Ask anything about employee attendance, ratings, burnout risk, or uploaded files..."
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={loading}
          />
          <button type="submit" className="btn-primary" disabled={loading || !input.trim()}>
            <Send size={16} />
            <span>Send</span>
          </button>
        </form>
      </div>
    </div>
  );
}
