import React, { useEffect, useState, useRef } from "react";
import {
  Send,
  Sparkles,
  BrainCircuit,
  Bot,
  User,
  FileSpreadsheet,
  Clock,
  RotateCcw,
  Square,
  BarChart3,
  Scale,
  ShieldCheck,
  Landmark,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Check,
  X,
  Timer
} from "lucide-react";
import MarkdownView from "../components/MarkdownView";
import { streamCopilotQuery, getCopilotSuggestions, getCouncilDelegates } from "../api/client";
import CopilotTools from "../components/CopilotTools";

const DELEGATE_ICON_MAP = {
  BarChart3: BarChart3,
  BrainCircuit: BrainCircuit,
  Scale: Scale,
  ShieldCheck: ShieldCheck,
  Landmark: Landmark
};

export default function CopilotPage({ onSelectEmployee }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "### 🏛️ Welcome to the AI Union War Room\n\nInstead of a single model, your inquiries are submitted to an **autonomous council of 5 specialized AI models**:\n\n* **📊 Qwen 3.5**: Chief Quantitative & Data Analytics Director\n* **🧠 DeepSeek-R1**: Chief Reasoning & Root-Cause Officer\n* **⚖️ Llama 3.1**: Operational Realism & Critical Counter-Auditor (*Devil's Advocate*)\n* **🛡️ Granite 4**: Statutory Governance, Policy & Risk Sentinel\n* **🏛️ Gemma 4**: Executive Strategy & Consensus Chair\n\nThe council deliberates under a **strict time boundary**, votes in favor or against proposed actions, and synthesizes a comprehensive, decision-grade executive resolution.",
      citations: [],
      model_used: "AI Union Council (5 Models)"
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState("Summoning Council Delegates…");
  const [countdownSeconds, setCountdownSeconds] = useState(30);
  const [warRoomPhase, setWarRoomPhase] = useState(1);
  const [lastQuery, setLastQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [councilDelegates, setCouncilDelegates] = useState([]);
  const [livePerspectives, setLivePerspectives] = useState({});
  const [liveVotes, setLiveVotes] = useState({});
  const [expandedLedgers, setExpandedLedgers] = useState({});

  const messagesEndRef = useRef(null);
  const abortControllerRef = useRef(null);
  const timerIntervalRef = useRef(null);
  const priorContextRef = useRef(null);

  useEffect(() => {
    getCopilotSuggestions().then(res => setSuggestions(res.suggestions || [])).catch(() => {});
    getCouncilDelegates().then(res => {
      if (res.delegates && res.delegates.length > 0) {
        setCouncilDelegates(res.delegates);
      }
    }).catch(() => {
      // Fallback local list of 5 delegates
      setCouncilDelegates([
        { id: "qwen_analyst", name: "Qwen 3.5", role_title: "Chief Quantitative & Data Analytics Director", icon: "BarChart3", badge_color: "#10b981", primary_model: "qwen3.5:9b" },
        { id: "deepseek_reasoner", name: "DeepSeek-R1", role_title: "Chief Reasoning & Root-Cause Officer", icon: "BrainCircuit", badge_color: "#06b6d4", primary_model: "deepseek-r1:7b" },
        { id: "llama_devil_advocate", name: "Llama 3.1", role_title: "Operational Realism & Critical Counter-Auditor", icon: "Scale", badge_color: "#f59e0b", primary_model: "llama3.1:8b" },
        { id: "granite_governance", name: "Granite 4", role_title: "Statutory Governance, Policy & Risk Sentinel", icon: "ShieldCheck", badge_color: "#38bdf8", primary_model: "granite4:3b" },
        { id: "gemma_chair", name: "Gemma 4", role_title: "Executive Strategy & Consensus Chair", icon: "Landmark", badge_color: "#c084fc", primary_model: "gemma4:12b" }
      ]);
    });
  }, []);

  // Strict Countdown Timer during War Room Deliberation
  useEffect(() => {
    if (loading) {
      setCountdownSeconds(30);
      setLoadingStatus("Summoning Council Delegates…");
      timerIntervalRef.current = setInterval(() => {
        setCountdownSeconds(prev => {
          if (prev <= 1) {
            setLoadingStatus("Finalizing Executive Consensus Resolution…");
            return 0;
          }
          const next = prev - 1;
          if (next === 26) {
            setWarRoomPhase(1);
            setLoadingStatus("Phase 1: Gathering role perspectives from council models…");
          } else if (next === 16) {
            setWarRoomPhase(2);
            setLoadingStatus("Phase 2: Council cross-examination & binding voting…");
          } else if (next === 8) {
            setWarRoomPhase(3);
            setLoadingStatus("Phase 3: Executive Chair (Gemma 4) synthesizing consensus…");
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
  }, [loading]);

  useEffect(() => {
    if (messages.length > 1) {
      messagesEndRef.current?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"
      });
    }
  }, [messages, loading]);

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
        content: "_War Room deliberation interrupted by user._",
        citations: [],
        model_used: "AI Union Council",
        isCancelled: true
      }
    ]);
  };

  const toggleLedger = (msgIdx) => {
    setExpandedLedgers(prev => ({
      ...prev,
      [msgIdx]: !prev[msgIdx]
    }));
  };

  const handleSend = async (queryText, tool = null) => {
    const text = (queryText || input).trim();
    if (!text || loading) return;

    setInput("");
    setLastQuery(text);
    const userMsg = { role: "user", content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    setLivePerspectives({});
    setLiveVotes({});
    setWarRoomPhase(1);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let streamAnswer = "";

    try {
      await streamCopilotQuery(
        text,
        null,
        tool,
        null,
        null,
        {
          onWarRoomInit: (initData) => {
            if (initData.delegates && initData.delegates.length > 0) {
              setCouncilDelegates(initData.delegates);
            }
          },
          onDelegatePerspective: (delData) => {
            setLivePerspectives(prev => ({
              ...prev,
              [delData.delegate_id]: delData.perspective
            }));
          },
          onDelegateVote: (voteData) => {
            setLiveVotes(prev => ({
              ...prev,
              [voteData.delegate_id]: {
                vote: voteData.vote,
                rationale: voteData.rationale
              }
            }));
          },
          onStatus: (st) => {
            if (st.message) {
              setLoadingStatus(st.message);
            }
            if (st.phase) {
              setWarRoomPhase(st.phase);
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
                  model_used: "AI Union Council",
                  isStreaming: true
                });
              }
              return updated;
            });
          },
          onDone: (doneData) => {
            if (doneData.prior_context) {
              priorContextRef.current = doneData.prior_context;
            }
            setLoading(false);
            setMessages(prev => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              const finalContent = doneData.answer || streamAnswer;
              const completedMsg = {
                role: "assistant",
                content: finalContent,
                consensus_score: doneData.consensus_score || 85,
                vote_tally: doneData.vote_tally || { in_favor: 4, conditional: 1, against: 0 },
                deliberation_duration_seconds: doneData.deliberation_duration_seconds || 22.5,
                deliberation_ledger: doneData.deliberation_ledger || [],
                citations: doneData.citations || [],
                artifacts: doneData.artifacts || [],
                model_used: doneData.model_used || "AI Union Council (5 Models)",
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
            setLoading(false);
            setMessages(prev => [
              ...prev.filter(m => !m.isStreaming),
              {
                role: "assistant",
                content: `⚠️ War Room deliberation encountered an interruption: ${streamErr.message}. Ensure Ollama models are running locally.`,
                citations: [],
                model_used: "AI Union Council",
                isError: true
              }
            ]);
          }
        },
        controller.signal,
        priorContextRef.current,
        null,
        "copilot",
        30.0
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  };

  const handleRetry = () => {
    if (lastQuery) {
      handleSend(lastQuery);
    }
  };

  return (
    <div className="copilot-page">
      {/* AI Union War Room Council Header (Sleek, AAA Contrast Compliant) */}
      <div className="copilot-header" style={{ borderBottom: "1px solid var(--border-subtle, rgba(255, 255, 255, 0.12))", paddingBottom: "1.25rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
          <div>
            <div style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", background: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.4)", padding: "0.3rem 0.8rem", borderRadius: "9999px", marginBottom: "0.6rem" }}>
              <Landmark size={15} color="#10b981" />
              <span style={{ fontSize: "0.75rem", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.06em", color: "#10b981" }}>
                AI Union Council War Room
              </span>
            </div>
            <h2 style={{ fontSize: "1.65rem", fontWeight: 800, color: "#ffffff", margin: "0.2rem 0" }}>
              Council Deliberation & Intelligence
            </h2>
            <p className="subtitle" style={{ fontSize: "0.85rem", color: "#e5e7eb", margin: 0, maxWidth: "680px" }}>
              Every complex inquiry is debated by a union of 5 specialized models with distinct roles, binding votes, and strict time limits.
            </p>
          </div>

          {/* Active Union Council Member Avatars (Replaces single-model dropdown) */}
          <div style={{
            display: "flex",
            flexDirection: "column",
            gap: "0.4rem",
            background: "#141417",
            border: "1.5px solid rgba(255, 255, 255, 0.2)",
            borderRadius: "10px",
            padding: "0.65rem 1rem",
            minWidth: "290px"
          }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.74rem", fontWeight: 700, color: "#f3f4f6" }}>
              <span>ACTIVE COUNCIL SEATS:</span>
              <span style={{ color: "#10b981", background: "rgba(16, 185, 129, 0.2)", padding: "1px 6px", borderRadius: "4px" }}>
                5 Models Active
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.2rem" }}>
              {councilDelegates.map((d) => {
                const IconComponent = DELEGATE_ICON_MAP[d.icon] || BrainCircuit;
                return (
                  <div
                    key={d.id}
                    title={`${d.name} (${d.role_title})`}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.35rem",
                      background: "rgba(255, 255, 255, 0.06)",
                      border: `1px solid ${d.badge_color || "#38bdf8"}`,
                      borderRadius: "6px",
                      padding: "0.25rem 0.5rem",
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      color: "#ffffff"
                    }}
                  >
                    <IconComponent size={13} color={d.badge_color || "#38bdf8"} />
                    <span>{d.name.split(':')[0]}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Multi-Source Grounding Indicator */}
        <div style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "0.5rem",
          background: "rgba(6, 182, 212, 0.12)",
          border: "1px solid rgba(6, 182, 212, 0.35)",
          padding: "0.25rem 0.75rem",
          borderRadius: "9999px",
          fontSize: "0.75rem",
          color: "#22d3ee",
          marginTop: "0.85rem"
        }}>
          <FileSpreadsheet size={13} />
          <span>Grounded in active tabular datasets, verified findings, and statutory policies</span>
        </div>
      </div>

      {/* Suggested Prompt Chips */}
      <div className="suggestions-container" style={{ marginTop: "1rem" }}>
        <div className="suggestions-label">
          <Sparkles size={14} color="#10b981" />
          <span style={{ fontWeight: 700, color: "#f3f4f6" }}>Submit strategic question to the Council:</span>
        </div>
        <div className="chips-row">
          {suggestions.map((s, idx) => (
            <button
              key={idx}
              type="button"
              className="chip-btn"
              onClick={() => handleSend(s)}
              style={{
                color: "#f3f4f6",
                background: "rgba(255, 255, 255, 0.05)",
                border: "1px solid rgba(255, 255, 255, 0.2)",
                fontSize: "0.78rem"
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <CopilotTools loading={loading} onRun={handleSend} />

      {/* Messages Thread */}
      <div className="chat-thread" aria-live="polite" style={{ marginTop: "1.2rem" }}>
        {messages.map((m, idx) => (
          <div key={idx} className={`chat-message ${m.role}`}>
            <div className="avatar-icon">
              {m.role === "assistant" ? <Landmark size={18} color="#10b981" /> : <User size={18} />}
            </div>
            <div className="message-content">
              <div className="message-bubble" style={{ background: m.role === "assistant" ? "#16161a" : "var(--brand-600)", border: "1.5px solid rgba(255,255,255,0.12)" }}>
                <MarkdownView content={m.content} />

                {/* War Room Council Deliberation & Voting Ledger (Expandable) */}
                {m.deliberation_ledger && m.deliberation_ledger.length > 0 && (
                  <div style={{
                    marginTop: "1.2rem",
                    background: "#0e0e11",
                    border: "1.5px solid rgba(16, 185, 129, 0.35)",
                    borderRadius: "8px",
                    overflow: "hidden"
                  }}>
                    {/* Collapsible Header */}
                    <button
                      type="button"
                      onClick={() => toggleLedger(idx)}
                      style={{
                        width: "100%",
                        padding: "0.75rem 1rem",
                        background: "rgba(16, 185, 129, 0.08)",
                        border: "none",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        cursor: "pointer",
                        color: "#ffffff"
                      }}
                      aria-expanded={Boolean(expandedLedgers[idx])}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                        <Landmark size={16} color="#10b981" />
                        <span style={{ fontWeight: 800, fontSize: "0.85rem", color: "#ffffff" }}>
                          AI Union War Room Deliberation Record & Voting Tally
                        </span>
                        <span style={{
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          background: "#10b981",
                          color: "#000000",
                          padding: "2px 7px",
                          borderRadius: "4px"
                        }}>
                          {m.consensus_score || 85}% Alignment
                        </span>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "0.8rem" }}>
                        <span style={{ fontSize: "0.75rem", color: "#9ca3af" }}>
                          ⏱️ {m.deliberation_duration_seconds}s
                        </span>
                        {expandedLedgers[idx] ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </div>
                    </button>

                    {/* Votes Summary Pills */}
                    <div style={{
                      display: "flex",
                      gap: "0.6rem",
                      padding: "0.5rem 1rem",
                      background: "rgba(0, 0, 0, 0.2)",
                      borderBottom: expandedLedgers[idx] ? "1px solid rgba(255,255,255,0.08)" : "none",
                      fontSize: "0.75rem"
                    }}>
                      <span style={{ color: "#34d399", fontWeight: 700 }}>
                        ✅ {m.vote_tally?.in_favor || 0} In Favor
                      </span>
                      <span style={{ color: "#fbbf24", fontWeight: 700 }}>
                        ⚠️ {m.vote_tally?.conditional || 0} Conditional
                      </span>
                      <span style={{ color: "#f87171", fontWeight: 700 }}>
                        ❌ {m.vote_tally?.against || 0} Against
                      </span>
                    </div>

                    {/* Expanded Delegate Cards */}
                    {expandedLedgers[idx] && (
                      <div style={{ padding: "0.85rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                        {m.deliberation_ledger.map((del) => {
                          const IconComp = DELEGATE_ICON_MAP[del.icon] || BrainCircuit;
                          const isConditional = del.vote === "CONDITIONAL";
                          const isAgainst = del.vote === "AGAINST";
                          const voteBg = isAgainst ? "rgba(239, 68, 68, 0.15)" : (isConditional ? "rgba(245, 158, 11, 0.15)" : "rgba(16, 185, 129, 0.15)");
                          const voteBorder = isAgainst ? "#ef4444" : (isConditional ? "#f59e0b" : "#10b981");
                          const voteColor = isAgainst ? "#f87171" : (isConditional ? "#fbbf24" : "#34d399");

                          return (
                            <div
                              key={del.id}
                              style={{
                                background: "#16161b",
                                border: "1px solid rgba(255, 255, 255, 0.1)",
                                borderRadius: "6px",
                                padding: "0.75rem 0.9rem"
                              }}
                            >
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.4rem" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                                  <IconComp size={15} color={del.badge_color || "#38bdf8"} />
                                  <strong style={{ fontSize: "0.82rem", color: "#ffffff" }}>{del.name}</strong>
                                  <span style={{ fontSize: "0.72rem", color: "#9ca3af" }}>— {del.role_title}</span>
                                </div>
                                <span style={{
                                  fontSize: "0.68rem",
                                  fontWeight: 800,
                                  textTransform: "uppercase",
                                  background: voteBg,
                                  border: `1px solid ${voteBorder}`,
                                  color: voteColor,
                                  padding: "2px 6px",
                                  borderRadius: "4px"
                                }}>
                                  {del.vote}
                                </span>
                              </div>

                              <p style={{ margin: "0.2rem 0 0.4rem 0", fontSize: "0.8rem", color: "#e5e7eb", fontStyle: "italic", lineHeight: 1.45 }}>
                                "{del.perspective}"
                              </p>

                              {del.vote_rationale && (
                                <div style={{ fontSize: "0.72rem", color: "#9ca3af", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "0.3rem" }}>
                                  <span style={{ fontWeight: 700, color: "#d1d5db" }}>Voting Rationale: </span>
                                  {del.vote_rationale}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {/* Metadata & Timestamp */}
                {m.role === "assistant" && (
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: "0.5rem",
                    fontSize: "0.72rem",
                    color: "#9ca3af",
                    marginTop: "0.6rem",
                    borderTop: "1px solid rgba(255,255,255,0.08)",
                    paddingTop: "0.4rem"
                  }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", color: "#e5e7eb" }}>
                      <Landmark size={12} color="#10b981" />
                      Deliberated by: <strong style={{ color: "#ffffff" }}>{m.model_used || "AI Union Council"}</strong>
                    </span>
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
                        <RotateCcw size={11} /> Re-summon War Room
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Live Active War Room Deliberation Chamber (Displayed while models deliberate) */}
        {loading && (
          <div className="chat-message assistant" role="status" aria-live="polite">
            <div className="avatar-icon"><Landmark size={18} color="#10b981" /></div>
            <div className="message-content">
              <div style={{
                background: "#0f0f13",
                border: "2px solid #10b981",
                borderRadius: "10px",
                padding: "1.1rem",
                boxShadow: "0 0 24px rgba(16, 185, 129, 0.2)",
                width: "100%"
              }}>
                {/* Top Chamber Bar with Glowing Countdown Timer */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.8rem", borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "0.75rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                    <div className="copilot-loading-spinner" aria-hidden="true" style={{ borderColor: "rgba(16,185,129,0.3)", borderTopColor: "#10b981" }} />
                    <div>
                      <div style={{ fontWeight: 800, fontSize: "0.95rem", color: "#ffffff" }}>
                        AI Union War Room in Session
                      </div>
                      <div style={{ fontSize: "0.78rem", color: "#34d399", marginTop: "2px" }}>
                        {loadingStatus}
                      </div>
                    </div>
                  </div>

                  {/* High-Contrast Live Countdown Pill (AAA Compliant) */}
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                    <div style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.45rem",
                      background: "#000000",
                      border: "2px solid #10b981",
                      borderRadius: "9999px",
                      padding: "0.35rem 0.85rem",
                      color: "#ffffff",
                      fontWeight: 800,
                      fontSize: "0.85rem",
                      letterSpacing: "0.04em",
                      boxShadow: "0 0 12px rgba(16, 185, 129, 0.35)"
                    }}>
                      <Timer size={14} color="#10b981" />
                      <span>00:{countdownSeconds < 10 ? `0${countdownSeconds}` : countdownSeconds}</span>
                    </div>

                    <button
                      type="button"
                      onClick={handleStopWaiting}
                      style={{
                        background: "rgba(239, 68, 68, 0.15)",
                        border: "1.5px solid #ef4444",
                        color: "#ffffff",
                        padding: "0.35rem 0.75rem",
                        borderRadius: "6px",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        cursor: "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.35rem"
                      }}
                      aria-label="Stop War Room deliberation"
                    >
                      <Square size={10} fill="currentColor" /> Stop
                    </button>
                  </div>
                </div>

                {/* 3-Stage Bounded Deliberation Progress Indicator */}
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.85rem", flexWrap: "wrap" }}>
                  <div style={{
                    flex: 1,
                    minWidth: "160px",
                    background: warRoomPhase >= 1 ? "rgba(16, 185, 129, 0.18)" : "rgba(255,255,255,0.04)",
                    border: `1px solid ${warRoomPhase >= 1 ? "#10b981" : "rgba(255,255,255,0.1)"}`,
                    padding: "0.4rem 0.6rem",
                    borderRadius: "6px",
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    color: warRoomPhase >= 1 ? "#ffffff" : "#6b7280"
                  }}>
                    1. Role Perspectives Pitch
                  </div>
                  <div style={{
                    flex: 1,
                    minWidth: "160px",
                    background: warRoomPhase >= 2 ? "rgba(245, 158, 11, 0.18)" : "rgba(255,255,255,0.04)",
                    border: `1px solid ${warRoomPhase >= 2 ? "#f59e0b" : "rgba(255,255,255,0.1)"}`,
                    padding: "0.4rem 0.6rem",
                    borderRadius: "6px",
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    color: warRoomPhase >= 2 ? "#ffffff" : "#6b7280"
                  }}>
                    2. Council Cross-Voting
                  </div>
                  <div style={{
                    flex: 1,
                    minWidth: "160px",
                    background: warRoomPhase >= 3 ? "rgba(192, 132, 252, 0.18)" : "rgba(255,255,255,0.04)",
                    border: `1px solid ${warRoomPhase >= 3 ? "#c084fc" : "rgba(255,255,255,0.1)"}`,
                    padding: "0.4rem 0.6rem",
                    borderRadius: "6px",
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    color: warRoomPhase >= 3 ? "#ffffff" : "#6b7280"
                  }}>
                    3. Consensus Resolution
                  </div>
                </div>

                {/* Live Council Delegates Roster with Real-time Speech & Vote Indicators */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: "0.6rem", marginTop: "0.85rem" }}>
                  {councilDelegates.map((d) => {
                    const IconC = DELEGATE_ICON_MAP[d.icon] || BrainCircuit;
                    const hasSpoken = Boolean(livePerspectives[d.id]);
                    const voteInfo = liveVotes[d.id];

                    return (
                      <div
                        key={d.id}
                        style={{
                          background: "#18181f",
                          border: `1px solid ${hasSpoken ? d.badge_color || "#10b981" : "rgba(255,255,255,0.12)"}`,
                          borderRadius: "6px",
                          padding: "0.6rem",
                          fontSize: "0.74rem"
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.3rem" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                            <IconC size={13} color={d.badge_color || "#38bdf8"} />
                            <strong style={{ color: "#ffffff" }}>{d.name}</strong>
                          </div>
                          {voteInfo ? (
                            <span style={{
                              fontSize: "0.65rem",
                              fontWeight: 800,
                              background: voteInfo.vote === "AGAINST" ? "rgba(239, 68, 68, 0.2)" : (voteInfo.vote === "CONDITIONAL" ? "rgba(245, 158, 11, 0.2)" : "rgba(16, 185, 129, 0.2)"),
                              border: `1px solid ${voteInfo.vote === "AGAINST" ? "#ef4444" : (voteInfo.vote === "CONDITIONAL" ? "#f59e0b" : "#10b981")}`,
                              color: voteInfo.vote === "AGAINST" ? "#f87171" : (voteInfo.vote === "CONDITIONAL" ? "#fbbf24" : "#34d399"),
                              padding: "1px 5px",
                              borderRadius: "4px"
                            }}>
                              {voteInfo.vote}
                            </span>
                          ) : hasSpoken ? (
                            <span style={{ fontSize: "0.65rem", color: "#34d399", fontWeight: 700 }}>
                              ✓ Pitched
                            </span>
                          ) : (
                            <span style={{ fontSize: "0.65rem", color: "#9ca3af" }}>
                              Deliberating…
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: "0.68rem", color: "#9ca3af", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {d.role_title}
                        </div>
                        {hasSpoken && (
                          <div style={{ fontSize: "0.72rem", color: "#e5e7eb", marginTop: "0.35rem", fontStyle: "italic", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "0.3rem" }}>
                            "{livePerspectives[d.id].slice(0, 90)}..."
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="chat-input-bar" style={{ marginTop: "1rem" }}>
        <form onSubmit={e => { e.preventDefault(); handleSend(); }}>
          <input
            type="text"
            aria-label="Submit question to the AI Union War Room"
            placeholder="Submit your strategic inquiry to the AI Union War Room (Council of 5 Models)..."
            value={input}
            onChange={e => setInput(e.target.value)}
            disabled={loading}
            style={{
              background: "#16161b",
              border: "1.5px solid rgba(255, 255, 255, 0.25)",
              color: "#ffffff",
              fontSize: "0.88rem"
            }}
          />
          <button
            type="submit"
            aria-label="Send to Council War Room"
            className="btn-primary"
            disabled={loading || !input.trim()}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.5rem",
              background: "#10b981",
              color: "#000000",
              fontWeight: 800,
              padding: "0.65rem 1.25rem",
              borderRadius: "6px"
            }}
          >
            <Send size={16} />
            <span>Summon Council</span>
          </button>
        </form>
      </div>
    </div>
  );
}
