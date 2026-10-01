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
  Clock,
  Volume2,
  BarChart3,
  Scale,
  ShieldCheck,
  Landmark,
  ChevronDown,
  ChevronUp,
  Timer,
  Layers,
  Activity,
  CheckCircle2,
  Trophy,
  Vote,
  FileText
} from 'lucide-react';
import MarkdownView from './MarkdownView';
import { askCopilot, streamCopilotQuery, getCopilotSuggestions, getCouncilDelegates } from '../api/client';
import CopilotTools from './CopilotTools';
import AnimatedAcousticOrb from './presentation/AnimatedAcousticOrb.jsx';
import { speakHridayIntro, HRIDAY_ACRONYM, HRIDAY_INTRO_SCRIPT } from '../utils/hridayVoice';

const DELEGATE_ICON_MAP = {
  BarChart3: BarChart3,
  BrainCircuit: BrainCircuit,
  Scale: Scale,
  ShieldCheck: ShieldCheck,
  Landmark: Landmark
};

export default function GlobalCopilotWidget({
  isOpen = false,
  onToggle,
  onClose,
  activeDatasetId = null,
  activeSheetId = null,
  activeSnapshotId = null,
  activePage = 'overview',
  activeSheetName = '',
  onSelectEmployee
}) {
  const [presentationVoiceActive, setPresentationVoiceActive] = useState(false);
  useEffect(() => {
    const listener = event => setPresentationVoiceActive(Boolean(event.detail));
    document.addEventListener("presentation-presenter", listener);
    return () => document.removeEventListener("presentation-presenter", listener);
  }, []);

  const [panelOpen, setPanelOpen] = useState(isOpen);
  const [minimized, setMinimized] = useState(false);
  const [isExpandedWidth, setIsExpandedWidth] = useState(false);
  const [hasPlayedIntro, setHasPlayedIntro] = useState(false);
  const [isVoiceSpeaking, setIsVoiceSpeaking] = useState(false);
  const stopVoiceRef = useRef(null);

  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hi, I’m **HRIDAY** — *Human Reasoning Intelligence, Dedicated to Assisting You*.\n\nI summon the **AI Union Council** across 5 specialized local models (Quantitative Analytics, Deductive Logic, Operational Realism, Governance Sentinel, and Executive Strategy Chair).\n\nFor each question, all models formulate **possible candidate answers**, evaluate their merits, and **cast binding ballots to elect the best Replier** among them.\n\nAsk me any complex question about your **uploaded spreadsheets**, workforce metrics, or strategy.',
      citations: [],
      model_used: 'HRIDAY · AI Union Council'
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState('Summoning Council Delegates…');
  const [countdownSeconds, setCountdownSeconds] = useState(60);
  const [warRoomPhase, setWarRoomPhase] = useState(1);
  const [lastQuery, setLastQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [councilDelegates, setCouncilDelegates] = useState([]);
  const [livePerspectives, setLivePerspectives] = useState({});
  const [liveVotes, setLiveVotes] = useState({});
  const [expandedLedgers, setExpandedLedgers] = useState({});
  const [expandedBallots, setExpandedBallots] = useState({});
  const [expandedProposals, setExpandedProposals] = useState({});
  const [activeProposalTabs, setActiveProposalTabs] = useState({});

  const messagesEndRef = useRef(null);
  const launcherRef = useRef(null);
  const chatInputRef = useRef(null);
  const abortControllerRef = useRef(null);
  const timerIntervalRef = useRef(null);
  const priorContextRef = useRef(null);

  const handleOpen = () => {
    setPanelOpen(true);
    setMinimized(false);
    onToggle?.(true);
    if (!hasPlayedIntro) {
      setHasPlayedIntro(true);
      try {
        stopVoiceRef.current = speakHridayIntro(
          () => setIsVoiceSpeaking(true),
          () => setIsVoiceSpeaking(false)
        );
      } catch (err) {
        console.warn("Spoken intro suppressed:", err);
      }
    }
  };

  const handleClose = () => {
    setPanelOpen(false);
    onClose?.();
    if (stopVoiceRef.current) {
      try {
        stopVoiceRef.current();
      } catch {}
      stopVoiceRef.current = null;
    }
    setIsVoiceSpeaking(false);
  };

  const handleReplayVoiceIntro = () => {
    if (isVoiceSpeaking && stopVoiceRef.current) {
      try {
        stopVoiceRef.current();
      } catch {}
      stopVoiceRef.current = null;
      setIsVoiceSpeaking(false);
      return;
    }
    try {
      stopVoiceRef.current = speakHridayIntro(
        () => setIsVoiceSpeaking(true),
        () => setIsVoiceSpeaking(false)
      );
    } catch (err) {
      console.warn("Spoken voice intro error:", err);
    }
  };

  useEffect(() => {
    setPanelOpen(isOpen);
  }, [isOpen]);

  useEffect(() => {
    getCopilotSuggestions().then((res) => setSuggestions(res.suggestions || [])).catch(() => {});
    getCouncilDelegates().then((res) => {
      if (res.delegates && res.delegates.length > 0) {
        setCouncilDelegates(res.delegates);
      }
    }).catch(() => {
      setCouncilDelegates([
        { id: "qwen_analyst", name: "Qwen 3.5", role_title: "Quantitative Analytics Director", icon: "BarChart3", badge_color: "#10b981", primary_model: "qwen3.5:9b" },
        { id: "deepseek_reasoner", name: "DeepSeek-R1", role_title: "Deductive Logic Officer", icon: "BrainCircuit", badge_color: "#06b6d4", primary_model: "deepseek-r1:7b" },
        { id: "llama_devil_advocate", name: "Llama 3.1", role_title: "Devil's Advocate & Realism", icon: "Scale", badge_color: "#f59e0b", primary_model: "llama3.1:8b" },
        { id: "granite_governance", name: "Granite 4", role_title: "Governance & Risk Sentinel", icon: "ShieldCheck", badge_color: "#38bdf8", primary_model: "granite4:3b" },
        { id: "gemma_chair", name: "Gemma 4", role_title: "Executive Strategy Chair", icon: "Landmark", badge_color: "#c084fc", primary_model: "gemma4:12b" }
      ]);
    });
  }, []);

  // Strict Countdown Timer during War Room Deliberation
  useEffect(() => {
    if (loading) {
      setCountdownSeconds(60);
      setLoadingStatus("Summoning Council Delegates…");
      timerIntervalRef.current = setInterval(() => {
        setCountdownSeconds((prev) => {
          if (prev <= 1) {
            setLoadingStatus("Finalizing Replier election outcome…");
            return 0;
          }
          const next = prev - 1;
          if (next === 56) {
            setWarRoomPhase(1);
            setLoadingStatus("Phase 1: Council models formulating 5 candidate answers…");
          } else if (next === 25) {
            setWarRoomPhase(2);
            setLoadingStatus("Phase 2: Council delegates voting on proposed answers to elect Replier…");
          } else if (next === 10) {
            setWarRoomPhase(3);
            setLoadingStatus("Phase 3: Tallying ballots & delivering Elected Replier response…");
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
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
      });
    }
  }, [messages, loading]);

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
        content: '_War Room deliberation interrupted by user._',
        citations: [],
        model_used: 'AI Union Council',
        isCancelled: true
      }
    ]);
  };

  const toggleLedger = (msgIdx) => {
    setExpandedLedgers((prev) => ({
      ...prev,
      [msgIdx]: !prev[msgIdx]
    }));
  };

  const toggleBallots = (msgIdx) => {
    setExpandedBallots((prev) => ({
      ...prev,
      [msgIdx]: !prev[msgIdx]
    }));
  };

  const toggleProposals = (msgIdx) => {
    setExpandedProposals((prev) => ({
      ...prev,
      [msgIdx]: !prev[msgIdx]
    }));
  };

  const setProposalTab = (msgIdx, candId) => {
    setActiveProposalTabs((prev) => ({
      ...prev,
      [msgIdx]: candId
    }));
  };

  const handleSend = async (queryText, tool = null) => {
    const text = (queryText || input).trim();
    if (!text || loading) return;

    setInput('');
    setLastQuery(text);
    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setLivePerspectives({});
    setLiveVotes({});
    setWarRoomPhase(1);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let streamAnswer = '';

    try {
      await streamCopilotQuery(
        text,
        null,
        tool,
        activeDatasetId,
        activeSheetId,
        {
          onWarRoomInit: (initData) => {
            if (initData.delegates && initData.delegates.length > 0) {
              setCouncilDelegates(initData.delegates);
            }
          },
          onDelegatePerspective: (delData) => {
            setLivePerspectives((prev) => ({
              ...prev,
              [delData.delegate_id]: delData.perspective
            }));
          },
          onDelegateVote: (voteData) => {
            setLiveVotes((prev) => ({
              ...prev,
              [voteData.delegate_id]: {
                vote: voteData.vote,
                voted_for: voteData.voted_for,
                voted_for_name: voteData.voted_for_name,
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
                  model_used: 'HRIDAY · AI Union Council',
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
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];
              const finalContent = doneData.answer || streamAnswer;
              const completedMsg = {
                role: 'assistant',
                content: finalContent,
                consensus_score: doneData.consensus_score || 85,
                vote_tally: doneData.vote_tally || { in_favor: 4, conditional: 1, against: 0 },
                deliberation_duration_seconds: doneData.deliberation_duration_seconds || 22.5,
                deliberation_ledger: doneData.deliberation_ledger || [],
                elected_replier: doneData.elected_replier || null,
                candidate_answers: doneData.candidate_answers || [],
                ballots: doneData.ballots || [],
                citations: doneData.citations || [],
                artifacts: doneData.artifacts || [],
                model_used: doneData.model_used || 'HRIDAY · AI Union Council (5 Models)',
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
            if (controller.signal.aborted) return;
            setLoading(false);
            setMessages((prev) => [
              ...prev.filter((m) => !m.isStreaming),
              {
                role: 'assistant',
                content: `⚠️ War Room deliberation encountered an interruption: ${streamErr.message}. Ensure Ollama models are running locally.`,
                citations: [],
                model_used: 'HRIDAY · AI Union Council',
                isError: true,
                failedQuery: text
              }
            ]);
          }
        },
        controller.signal,
        priorContextRef.current,
        activeSnapshotId,
        activePage,
        60.0
      );
    } catch (err) {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape' && panelOpen) {
      handleClose();
    }
  };

  if (presentationVoiceActive) return null;

  return (
    <>
      {/* 1. Backdrop for modal drawer on desktop and mobile */}
      {panelOpen && !minimized && (
        <div
          className="copilot-drawer-backdrop"
          onClick={handleClose}
          aria-label="Close HRIDAY"
          role="presentation"
        />
      )}

      {/* 2. Persistent Floating Launcher Button */}
      {!panelOpen && (
        <button
          ref={launcherRef}
          type="button"
          className="global-copilot-launcher hriday-global-launcher"
          onClick={handleOpen}
          aria-label="Open HRIDAY AI Assistant"
          title="Open HRIDAY (Human Reasoning Intelligence, Dedicated to Assisting You)"
          aria-expanded={false}
          aria-controls="copilot-drawer-panel"
        >
          <div className="hriday-launcher-heart">
            <AnimatedAcousticOrb compact isPlaying={isVoiceSpeaking} />
          </div>
          <div className="launcher-text-col">
            <span className="launcher-label">HRIDAY</span>
            <span className="launcher-sub">AI Union Council</span>
          </div>
          <span className="launcher-pulse" aria-hidden="true" />
        </button>
      )}

      {/* 3. Slide-out Copilot Panel */}
      {panelOpen && (
        <section
          id="copilot-drawer-panel"
          className={`copilot-drawer-panel hriday-drawer-panel ${minimized ? 'minimized' : ''} ${isExpandedWidth ? 'expanded-width' : ''}`}
          role="dialog"
          aria-label="HRIDAY AI Intelligence"
          aria-modal={!minimized}
          onKeyDown={handleKeyDown}
        >
          {/* Header */}
          <div className="copilot-drawer-header hriday-drawer-header">
            {/* Top row: Brand on left, window controls on right */}
            <div className="hriday-header-main-row">
              <div className="copilot-header-brand">
                <div className="hriday-header-heart-wrap" aria-hidden="true">
                  <AnimatedAcousticOrb compact isPlaying={isVoiceSpeaking} />
                </div>
                <div className="copilot-title-group">
                  <div className="copilot-title-row">
                    <h3>HRIDAY</h3>
                    <span className="hriday-council-badge">AI UNION WAR ROOM</span>
                    <button
                      type="button"
                      className="btn-hriday-voice-trigger"
                      onClick={handleReplayVoiceIntro}
                      title="Play HRIDAY Spoken Voice Introduction"
                    >
                      <Volume2 size={12} />
                      <span>{isVoiceSpeaking ? "Speaking…" : "Voice Intro"}</span>
                    </button>
                    {activeSheetName && (
                      <span className="copilot-context-badge" title={`Context: ${activeSheetName}`}>
                        <FileSpreadsheet size={11} aria-hidden="true" />
                        <span className="context-name">{activeSheetName}</span>
                      </span>
                    )}
                  </div>
                  <div className="hriday-motto-subtitle" title={HRIDAY_ACRONYM}>
                    Human Reasoning Intelligence · 5-Model Collective Quorum
                  </div>
                </div>
              </div>

              {/* Header Controls */}
              <div className="copilot-header-actions">
                <button
                  type="button"
                  className="header-ctrl-btn"
                  onClick={() => setIsExpandedWidth(!isExpandedWidth)}
                  title={isExpandedWidth ? 'Standard View (600px)' : 'Expanded Command Center (860px)'}
                  aria-label={isExpandedWidth ? 'Standard View' : 'Expanded Command Center'}
                >
                  {isExpandedWidth ? <Minimize2 size={15} aria-hidden="true" /> : <Maximize2 size={15} aria-hidden="true" />}
                </button>
                <button
                  type="button"
                  className="header-ctrl-btn"
                  onClick={() => setMinimized(!minimized)}
                  title={minimized ? 'Expand Copilot' : 'Minimize Copilot'}
                  aria-label={minimized ? 'Expand Copilot' : 'Minimize Copilot'}
                >
                  {minimized ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
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
            </div>

            {/* Bottom row: Council Quorum Strip */}
            <div className="hriday-council-bar">
              <div className="council-status-chip">
                <span className="quorum-pulse-dot" aria-hidden="true" />
                <span className="quorum-title">5-MODEL COUNCIL</span>
              </div>
              <div className="council-delegates-track" role="list">
                {councilDelegates.map((d) => {
                  const IconComp = DELEGATE_ICON_MAP[d.icon] || BrainCircuit;
                  const hasSpoken = Boolean(livePerspectives[d.id]);
                  const voteInfo = liveVotes[d.id];
                  return (
                    <div
                      key={d.id}
                      className={`council-delegate-badge ${hasSpoken ? 'active-spoken' : ''} ${voteInfo ? 'active-voted' : ''}`}
                      style={{ '--delegate-accent': d.badge_color || '#38bdf8' }}
                      role="listitem"
                      title={`${d.name} (${d.primary_model}) — ${d.role_title}`}
                    >
                      <IconComp size={11} className="delegate-badge-icon" />
                      <span className="delegate-badge-name">{d.name.split(':')[0]}</span>
                      <span className="delegate-badge-role">{d.role_title.split('&')[0].trim()}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Body (Hidden when minimized) */}
          {!minimized && (
            <div className="copilot-drawer-body">
              {/* Context bar if bound to sheet */}
              {activeSheetName && (
                <div className="copilot-sheet-banner">
                  <FileSpreadsheet size={13} aria-hidden="true" />
                  <span>Evaluating: <strong>{activeSheetName}</strong></span>
                </div>
              )}

              {/* Suggestions */}
              {messages.length <= 1 && suggestions.length > 0 && (
                <div className="copilot-suggestions-panel">
                  <span className="suggestions-prompt-title">
                    <Sparkles size={13} color="#10b981" /> Suggested Council Inquiries:
                  </span>
                  <div className="suggestions-chips-flex">
                    {suggestions.slice(0, 3).map((sug, sIdx) => (
                      <button
                        key={sIdx}
                        type="button"
                        className="suggestion-chip"
                        onClick={() => handleSend(sug)}
                      >
                        {sug}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <CopilotTools loading={loading} onRun={handleSend} />

              {/* Messages list */}
              <div
                className="copilot-messages-list"
                role="log"
                aria-live="polite"
                aria-label="HRIDAY conversation messages"
              >
                {messages.map((msg, idx) => (
                  <div key={idx} className={`copilot-msg-bubble ${msg.role}`}>
                    <div className={`msg-avatar ${msg.role === 'assistant' ? 'hriday-avatar' : 'user-avatar'}`} aria-hidden="true">
                      {msg.role === 'assistant' ? <Landmark size={15} color="#10b981" /> : <User size={15} />}
                    </div>
                    <div className="msg-content-wrap">
                      {/* Democratic Council Election Verdict Hero Card */}
                      {(msg.elected_replier || msg.consensus_score !== undefined) && (
                        <div className="elected-replier-hero-card">
                          <div className="hero-top-row">
                            <div className="hero-winner-badge">
                              <span className="trophy-badge-icon" aria-hidden="true">
                                <Trophy size={16} />
                              </span>
                              <div className="hero-winner-details">
                                <div className="hero-winner-title-row">
                                  <span className="hero-eyebrow">DEMOCRATICALLY ELECTED REPLIER</span>
                                  {msg.deliberation_duration_seconds && (
                                    <span className="hero-duration-chip">
                                      <Clock size={11} /> {msg.deliberation_duration_seconds}s
                                    </span>
                                  )}
                                </div>
                                <div className="hero-winner-name-row">
                                  <strong className="hero-winner-name">
                                    {msg.elected_replier?.name || 'DeepSeek-R1'}
                                  </strong>
                                  <span className="hero-winner-model">
                                    ({msg.elected_replier?.primary_model || 'deepseek-r1:7b'})
                                  </span>
                                  <span className="hero-winner-role">
                                    — {msg.elected_replier?.role_title || 'Deductive Logic Officer'}
                                  </span>
                                </div>
                              </div>
                            </div>

                            {/* Votes tally badge */}
                            <div className="hero-votes-summary">
                              <span className="hero-votes-pill">
                                🗳️ {msg.elected_replier?.votes_received || msg.vote_tally?.winner_votes || 3} of {msg.elected_replier?.total_votes || 5} Council Votes
                              </span>
                              <span className="hero-quorum-percentage">
                                {msg.elected_replier?.vote_percentage || msg.consensus_score || 60}% Majority Quorum
                              </span>
                            </div>
                          </div>

                          {/* Ballot Tally Breakdown Chips */}
                          {msg.candidate_answers && msg.candidate_answers.length > 0 && (
                            <div className="hero-candidate-tallies-row">
                              <span className="tally-lead-label">Ballot Tally:</span>
                              {msg.candidate_answers.map((c) => (
                                <span
                                  key={c.id}
                                  className={`cand-tally-pill ${c.is_elected ? 'is-winner' : ''}`}
                                  style={{ '--cand-color': c.badge_color || '#38bdf8' }}
                                >
                                  {c.is_elected && <Trophy size={10} className="pill-trophy" />}
                                  <span className="cand-pill-name">{c.name.split(':')[0]}</span>
                                  <strong className="cand-pill-votes">{c.votes_received} {c.votes_received === 1 ? 'vote' : 'votes'}</strong>
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Message Content (The Elected Replier's Winning Response) */}
                      <div className="msg-text markdown-body hriday-markdown">
                        <MarkdownView content={msg.content} />
                      </div>

                      {/* Accordion 1: Council Ballots & Voting Ledger */}
                      {msg.ballots && msg.ballots.length > 0 && (
                        <div className="council-ballots-accordion">
                          <button
                            type="button"
                            className="ballots-accordion-trigger"
                            onClick={() => toggleBallots(idx)}
                            aria-expanded={Boolean(expandedBallots[idx])}
                          >
                            <div className="trigger-left">
                              <Vote size={14} className="trigger-icon" />
                              <span className="trigger-text">
                                Council Ballot Ledger ({msg.ballots.length} Delegates Voted to Elect Replier)
                              </span>
                            </div>
                            <div className="trigger-right">
                              <span className="trigger-hint">{expandedBallots[idx] ? 'Hide Ballots' : 'Inspect Ballots'}</span>
                              {expandedBallots[idx] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </div>
                          </button>

                          {expandedBallots[idx] && (
                            <div className="ballots-entries-container">
                              {msg.ballots.map((ballot, bIdx) => {
                                const VoterIcon = DELEGATE_ICON_MAP[ballot.voter_icon] || BrainCircuit;
                                return (
                                  <div
                                    key={bIdx}
                                    className="ballot-card"
                                    style={{ '--voter-color': ballot.voter_badge_color || '#38bdf8' }}
                                  >
                                    <div className="ballot-card-header">
                                      <div className="voter-identity">
                                        <VoterIcon size={13} style={{ color: ballot.voter_badge_color || '#38bdf8' }} />
                                        <strong className="voter-name">{ballot.voter_name}</strong>
                                        <span className="voter-role">({ballot.voter_role})</span>
                                      </div>
                                      <div className="voted-for-pill">
                                        <span className="vote-arrow">voted for ➔</span>
                                        <strong
                                          className="voted-for-target"
                                          style={{ color: ballot.voted_for_badge_color || '#10b981' }}
                                        >
                                          {ballot.voted_for_name}
                                        </strong>
                                      </div>
                                    </div>
                                    {ballot.rationale && (
                                      <p className="ballot-rationale">
                                        <span className="rationale-tag">Rationale: </span>"{ballot.rationale}"
                                      </p>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Accordion 2: All 5 Candidate Proposed Answers */}
                      {msg.candidate_answers && msg.candidate_answers.length > 0 && (
                        <div className="candidate-proposals-accordion">
                          <button
                            type="button"
                            className="proposals-accordion-trigger"
                            onClick={() => toggleProposals(idx)}
                            aria-expanded={Boolean(expandedProposals[idx])}
                          >
                            <div className="trigger-left">
                              <FileText size={14} className="trigger-icon" />
                              <span className="trigger-text">
                                Compare All 5 Proposed Answers Drafted by Council Candidates
                              </span>
                            </div>
                            <div className="trigger-right">
                              <span className="trigger-hint">{expandedProposals[idx] ? 'Hide Proposals' : 'Review Proposals'}</span>
                              {expandedProposals[idx] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </div>
                          </button>

                          {expandedProposals[idx] && (
                            <div className="proposals-content-container">
                              {/* Tab buttons for all candidate models */}
                              <div className="proposal-tabs-bar" role="tablist">
                                {msg.candidate_answers.map((cand) => {
                                  const CandIcon = DELEGATE_ICON_MAP[cand.icon] || BrainCircuit;
                                  const currentActive = activeProposalTabs[idx] || (msg.elected_replier?.id || msg.candidate_answers[0].id);
                                  const isSelected = currentActive === cand.id;
                                  return (
                                    <button
                                      key={cand.id}
                                      type="button"
                                      role="tab"
                                      aria-selected={isSelected}
                                      className={`proposal-tab-btn ${isSelected ? 'active' : ''} ${cand.is_elected ? 'elected-tab' : ''}`}
                                      onClick={() => setProposalTab(idx, cand.id)}
                                      style={{ '--tab-accent': cand.badge_color || '#38bdf8' }}
                                    >
                                      <CandIcon size={12} />
                                      <span>{cand.name.split(':')[0]}</span>
                                      {cand.is_elected && <Trophy size={11} className="tab-trophy-icon" />}
                                      <span className="tab-votes-count">{cand.votes_received}v</span>
                                    </button>
                                  );
                                })}
                              </div>

                              {/* Selected Candidate's Full Answer Content */}
                              {(() => {
                                const currentActive = activeProposalTabs[idx] || (msg.elected_replier?.id || msg.candidate_answers[0].id);
                                const selectedCand = msg.candidate_answers.find((c) => c.id === currentActive) || msg.candidate_answers[0];
                                const CandIcon = DELEGATE_ICON_MAP[selectedCand.icon] || BrainCircuit;
                                return (
                                  <div className="selected-proposal-view" style={{ '--cand-border': selectedCand.badge_color || '#38bdf8' }}>
                                    <div className="selected-proposal-header">
                                      <div className="cand-info">
                                        <CandIcon size={14} style={{ color: selectedCand.badge_color || '#38bdf8' }} />
                                        <strong className="cand-title">{selectedCand.name}</strong>
                                        <span className="cand-model">({selectedCand.primary_model})</span>
                                        <span className="cand-role">— {selectedCand.role_title}</span>
                                      </div>
                                      <div className="cand-stats">
                                        {selectedCand.is_elected ? (
                                          <span className="elected-stamp">🏆 Elected Replier</span>
                                        ) : (
                                          <span className="runner-up-stamp">Alternative Proposal</span>
                                        )}
                                        <span className="cand-votes-badge">
                                          {selectedCand.votes_received} {selectedCand.votes_received === 1 ? 'Vote' : 'Votes'} Received
                                        </span>
                                      </div>
                                    </div>
                                    <div className="selected-proposal-text markdown-body hriday-markdown">
                                      <MarkdownView content={selectedCand.answer || 'No proposed answer recorded.'} />
                                    </div>
                                  </div>
                                );
                              })()}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Expandable Fallback Deliberation Transcript (if old message format without ballots) */}
                      {!msg.ballots && msg.deliberation_ledger && msg.deliberation_ledger.length > 0 && (
                        <div className="deliberation-ledger-accordion">
                          <button
                            type="button"
                            className="ledger-accordion-trigger"
                            onClick={() => toggleLedger(idx)}
                            aria-expanded={Boolean(expandedLedgers[idx])}
                          >
                            <div className="trigger-left">
                              <Layers size={13} color="#10b981" />
                              <span className="trigger-text">
                                Council Deliberation Transcript & Model Arguments ({msg.deliberation_ledger.length} Delegates)
                              </span>
                            </div>
                            <div className="trigger-right">
                              <span className="trigger-hint">{expandedLedgers[idx] ? 'Collapse' : 'Expand'}</span>
                              {expandedLedgers[idx] ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                            </div>
                          </button>

                          {expandedLedgers[idx] && (
                            <div className="ledger-entries-container">
                              {msg.deliberation_ledger.map((del) => {
                                const IconComp = DELEGATE_ICON_MAP[del.icon] || BrainCircuit;
                                const isConditional = del.vote === 'CONDITIONAL';
                                const isAgainst = del.vote === 'AGAINST';
                                const voteClass = isAgainst ? 'vote-against' : (isConditional ? 'vote-conditional' : 'vote-favor');

                                return (
                                  <div
                                    key={del.id}
                                    className="ledger-delegate-entry"
                                    style={{ '--delegate-border': del.badge_color || '#38bdf8' }}
                                  >
                                    <div className="entry-header">
                                      <div className="entry-identity">
                                        <IconComp size={13} style={{ color: del.badge_color || '#38bdf8' }} />
                                        <strong className="entry-name">{del.name}</strong>
                                        <span className="entry-model-tag">{del.primary_model}</span>
                                        <span className="entry-role">— {del.role_title}</span>
                                      </div>
                                      <span className={`entry-vote-tag ${voteClass}`}>
                                        {del.vote}
                                      </span>
                                    </div>

                                    {del.perspective && (
                                      <blockquote className="entry-perspective-quote">
                                        "{del.perspective}"
                                      </blockquote>
                                    )}

                                    {del.vote_rationale && (
                                      <div className="entry-rationale-box">
                                        <strong className="rationale-lbl">Vote Rationale: </strong>
                                        <span>{del.vote_rationale}</span>
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Supporting Citations */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="msg-citations-wrap">
                          <span className="citation-title">Supporting Spreadsheet Evidence:</span>
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
                        <span className="msg-model-tag-unified">
                          <Landmark size={11} color="#10b981" />
                          {msg.model_used || "HRIDAY · AI Union Council"}
                        </span>
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

                {/* Visible, Accessible Loading State with Countdown Timer & War Room Progress */}
                {loading && (
                  <div
                    className="copilot-msg-bubble assistant loading"
                    role="status"
                    aria-live="polite"
                    aria-label={`HRIDAY War Room Deliberating: ${loadingStatus}`}
                  >
                    <div className="msg-avatar hriday-avatar" aria-hidden="true">
                      <Landmark size={15} color="#10b981" />
                    </div>

                    <div className="war-room-deliberation-deck">
                      {/* Top Bar with Glowing Countdown Timer */}
                      <div className="deliberation-deck-header">
                        <div className="deck-title-group">
                          <div className="deliberation-live-beacon">
                            <span className="beacon-ring" />
                            <span className="beacon-core" />
                          </div>
                          <div>
                            <div className="deliberation-title">
                              AI Union Deliberation Active
                            </div>
                            <div className="deliberation-subtitle">
                              {loadingStatus}
                            </div>
                          </div>
                        </div>

                        {/* Live Countdown Pill & Stop Button */}
                        <div className="deliberation-header-actions">
                          <div className="deliberation-chronometer" title="Time remaining before consensus cutoff">
                            <Timer size={12} className="timer-icon" />
                            <span className="timer-digits">00:{countdownSeconds < 10 ? `0${countdownSeconds}` : countdownSeconds}</span>
                          </div>
                          <button
                            type="button"
                            className="btn-stop-deliberation"
                            onClick={handleStopWaiting}
                            title="Stop War Room deliberation"
                            aria-label="Stop waiting for response"
                          >
                            <Square size={10} fill="currentColor" /> Stop
                          </button>
                        </div>
                      </div>

                      {/* 3-Stage Progress Track */}
                      <div className="deliberation-stages-track">
                        <div className={`deliberation-stage-step ${warRoomPhase >= 1 ? 'active' : ''} ${warRoomPhase > 1 ? 'completed' : ''}`}>
                          <span className="step-num">1</span>
                          <span className="step-label">Drafting 5 Answers</span>
                        </div>
                        <div className="stage-step-divider" />
                        <div className={`deliberation-stage-step ${warRoomPhase >= 2 ? 'active' : ''} ${warRoomPhase > 2 ? 'completed' : ''}`}>
                          <span className="step-num">2</span>
                          <span className="step-label">Ballot & Election</span>
                        </div>
                        <div className="stage-step-divider" />
                        <div className={`deliberation-stage-step ${warRoomPhase >= 3 ? 'active' : ''}`}>
                          <span className="step-num">3</span>
                          <span className="step-label">Elected Replier</span>
                        </div>
                      </div>

                      {/* Live Delegate Proposed Answers & Ballot Voting Matrix */}
                      <div className="deliberation-delegates-grid">
                        {councilDelegates.map((d) => {
                          const IconC = DELEGATE_ICON_MAP[d.icon] || BrainCircuit;
                          const hasSpoken = Boolean(livePerspectives[d.id]);
                          const voteInfo = liveVotes[d.id];

                          return (
                            <div
                              key={d.id}
                              className={`deliberation-delegate-card ${hasSpoken ? 'card-spoken' : ''} ${voteInfo ? 'card-voted' : ''}`}
                              style={{ '--delegate-border-accent': d.badge_color || '#38bdf8' }}
                            >
                              <div className="del-card-header">
                                <div className="del-identity">
                                  <span className="del-icon-wrap" style={{ color: d.badge_color || '#38bdf8' }}>
                                    <IconC size={12} />
                                  </span>
                                  <strong className="del-name">{d.name}</strong>
                                  <span className="del-role">— {d.role_title.split('&')[0].trim()}</span>
                                </div>

                                <div className="del-status-badge">
                                  {voteInfo ? (
                                    <span className="del-vote-pill vote-favor">
                                      ➔ Voted for {voteInfo.voted_for_name || 'Replier'}
                                    </span>
                                  ) : hasSpoken ? (
                                    <span className="del-pitched-pill">
                                      ✓ Proposed Answer Drafted
                                    </span>
                                  ) : (
                                    <span className="del-thinking-pill">
                                      <span className="thinking-dots">Drafting Answer…</span>
                                    </span>
                                  )}
                                </div>
                              </div>

                              {hasSpoken && !voteInfo && livePerspectives[d.id] && (
                                <div className="del-perspective-preview">
                                  <span className="preview-label">Proposed: </span>"{livePerspectives[d.id].slice(0, 110)}…"
                                </div>
                              )}
                              {voteInfo && voteInfo.rationale && (
                                <div className="del-rationale-preview">
                                  <span className="rat-label">Vote Rationale: </span>{voteInfo.rationale.slice(0, 120)}…
                                </div>
                              )}
                            </div>
                          );
                        })}
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
                <div className="copilot-input-wrapper">
                  <input
                    ref={chatInputRef}
                    type="text"
                    className="copilot-text-input"
                    placeholder="Ask HRIDAY AI Union War Room (e.g. analyze attrition drivers, compensation disparity)…"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    disabled={loading}
                    aria-label="Query input"
                  />
                  <div className="input-keyboard-hint">
                    Press <strong>Enter ↵</strong> to deliberate · <strong>Esc</strong> to close
                  </div>
                </div>
                <button
                  type="submit"
                  className="copilot-send-btn"
                  disabled={!input.trim() || loading}
                  aria-label="Send query to Council"
                  title="Send query to Council"
                >
                  <Send size={16} aria-hidden="true" />
                </button>
              </form>
            </div>
          )}
        </section>
      )}
    </>
  );
}
