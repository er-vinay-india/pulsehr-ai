import React, { useState } from 'react';
import { Minimize2 } from 'lucide-react';
import AnimatedAcousticOrb from './AnimatedAcousticOrb';
import VoiceoverPlayer from '../VoiceoverPlayer';
import '../../styles/acoustic-orb.scss';

export default function AcousticOrbPresenter({ deckId, deckSpec, currentSlideOrder = 1 }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const slide = deckSpec?.slides?.[currentSlideOrder - 1];
  const text = [slide?.title, slide?.narration_script || slide?.narrative,
    ...(slide?.bullets || []).map(b => typeof b === 'string' ? b : b.text || '')].filter(Boolean).join('. ');
  return <div className={`acoustic-orb-presenter ${expanded ? 'expanded' : 'minimized'}`}>
    {!expanded && <button className="orb-trigger-btn" onClick={() => setExpanded(true)} aria-label="Open presentation voiceover">
      <span className="mini-canvas-wrap"><AnimatedAcousticOrb compact isPlaying={isPlaying} /></span>
      <span className="orb-badge-label"><span className="title">Executive AI Orb</span><span className="status"><span className="pulse-dot" />{isPlaying ? 'Speaking…' : 'Voiceover'}</span></span>
    </button>}
    <div className="orb-hud-card" style={{ display: expanded ? undefined : 'none' }}>
      <div className="orb-hud-header"><span className="hud-title">Slide {currentSlideOrder} voiceover</span>
        <button className="icon-btn" aria-label="Minimize voiceover" onClick={() => setExpanded(false)}><Minimize2 size={16} /></button>
      </div>
      {expanded && <div className="orb-visualizer-stage"><div className="orb-frequency-glow" /><AnimatedAcousticOrb isPlaying={isPlaying} /></div>}
      <div style={{ padding: 16 }}>
        <p style={{ fontSize: '.8rem', color: '#94a3b8' }}>Local device voice · reads the current slide</p>
        <VoiceoverPlayer onPlayingChange={setIsPlaying} text={text} identity={`${deckId}:${currentSlideOrder}`} label="Play slide voiceover" />
        <details style={{ marginTop: 12, fontSize: '.8rem' }}><summary>Transcript</summary><p>{text}</p></details>
      </div>
    </div>
  </div>;
}
