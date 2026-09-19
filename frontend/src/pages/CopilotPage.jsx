import React, { useEffect, useState, useRef } from "react";
import { Send, Sparkles, BrainCircuit, Bot, User, FileSpreadsheet, Cpu } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { askCopilot, getCopilotSuggestions, getAvailableModels } from "../api/client";

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
  const [suggestions, setSuggestions] = useState([]);
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem("pulsehr_selected_model") || "llama3.1:8b");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    getCopilotSuggestions().then(res => setSuggestions(res.suggestions || []));
    getAvailableModels().then(res => {
      const avail = res.models || [];
      setModels(avail);
      if (avail.length > 0) {
        const saved = localStorage.getItem("pulsehr_selected_model");
        const match = avail.find(m => m.id === saved) || avail[0];
        setSelectedModel(match.id);
      }
    });
  }, []);

  useEffect(() => {
    if (messages.length > 1) messagesEndRef.current?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, [messages, loading]);

  const handleModelChange = (modelId) => {
    setSelectedModel(modelId);
    localStorage.setItem("pulsehr_selected_model", modelId);
  };

  const handleSend = async (queryText, tool = null) => {
    const text = (queryText || input).trim();
    if (!text || loading) return;

    setInput("");
    const userMsg = { role: "user", content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await askCopilot(text, selectedModel, tool);
      const botMsg = {
        role: "assistant",
        content: res.answer,
        citations: res.citations || [],
        artifacts: res.artifacts || [],
        model_used: res.model_used || selectedModel
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ Failed to retrieve analysis: ${err.message}. Ensure Ollama or local engine is running.`,
          citations: [],
          model_used: selectedModel
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

          {/* Model Selector Dropdown */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            background: "var(--surface-card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            padding: "0.5rem 0.85rem"
          }}>
            <Cpu size={16} color="var(--brand-400)" />
            <span style={{ fontSize: "0.775rem", fontWeight: 700, color: "var(--fg-secondary)", textTransform: "uppercase" }}>
              Active Model:
            </span>
            <select
              aria-label="AI model"
              value={selectedModel}
              onChange={e => handleModelChange(e.target.value)}
              style={{
                background: "none",
                border: "none",
                color: "var(--fg-primary)",
                fontWeight: 700,
                fontSize: "0.85rem",
                outline: "none",
                cursor: "pointer"
              }}
            >
              {models.map(m => (
                <option key={m.id} value={m.id} style={{ background: "#1c1815", color: "#fff9f2" }}>
                  {m.name}
                </option>
              ))}
            </select>
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
      <div className="chat-thread">
        {messages.map((m, idx) => (
          <div key={idx} className={`chat-message ${m.role}`}>
            <div className="avatar-icon">
              {m.role === "assistant" ? <Bot size={18} /> : <User size={18} />}
            </div>
            <div className="message-content">
              <div className="message-bubble">
                <div className="markdown-content">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                  >
                    {m.content}
                  </ReactMarkdown>
                </div>
                {m.citations?.length > 0 && <details style={{ marginTop: 12 }}><summary>Source records ({m.citations.length})</summary>{m.citations.map(c => <div key={c.chunk_id} style={{ margin: '8px 0' }}><strong>{c.source_file} / {c.sheet_name}</strong>{c.type === 'exact_join' && <span> · Connected by exact key</span>}<p>{c.text}</p></div>)}</details>}
                {m.artifacts?.map(artifact => (
                  <a key={artifact.url} href={artifact.url} download className="chip-btn" style={{ display: 'inline-block', marginTop: 12 }}>Download PowerPoint</a>
                ))}
                {m.model_used && m.role === "assistant" && (
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.35rem",
                    fontSize: "0.7rem",
                    color: "var(--fg-secondary)",
                    marginTop: "0.6rem",
                    borderTop: "1px solid var(--border-subtle)",
                    paddingTop: "0.4rem"
                  }}>
                    <Cpu size={11} color="var(--brand-400)" />
                    <span>Answered by: <strong>{m.model_used}</strong></span>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="chat-message assistant">
            <div className="avatar-icon"><Bot size={18} /></div>
            <div className="message-content">
              <div className="message-bubble loading-bubble">
                <span className="dot-pulse" /> Preparing your answer…
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
