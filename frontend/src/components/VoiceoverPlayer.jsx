import React, { useEffect, useRef, useState } from 'react';
import { Volume2, Square } from 'lucide-react';

export default function VoiceoverPlayer({ text, identity, onEnded, label = 'Listen to summary' }) {
  const audio = useRef(null);
  const request = useRef(null);
  const url = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);

  const stop = () => {
    request.current?.abort();
    request.current = null;
    audio.current?.pause();
    if (audio.current) { audio.current.removeAttribute('src'); audio.current.load(); }
    if (url.current) URL.revokeObjectURL(url.current);
    url.current = null;
    setLoading(false);
    setReady(false);
  };
  useEffect(() => { stop(); setError(''); return stop; }, [identity, text]);

  const play = async () => {
    stop();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/api/analytics/decision-brief/voiceover', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }), signal: controller.signal
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(typeof detail.detail === 'string' ? detail.detail : 'Could not prepare voiceover. Please retry.');
      }
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      url.current = URL.createObjectURL(blob);
      audio.current.src = url.current;
      setReady(true);
      try { await audio.current.play(); }
      catch { setError('Audio is ready. Press Play in the audio controls to start.'); }
    } catch (err) {
      if (!controller.signal.aborted) setError(err.message);
    } finally {
      if (request.current === controller) setLoading(false);
    }
  };

  return <div className="voiceover-player" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, maxWidth: '100%' }}>
    <button type="button" onClick={play} disabled={loading || !text?.trim()}><Volume2 size={16} /> {loading ? 'Preparing voiceover…' : ready ? 'Restart voiceover' : label}</button>
    {(loading || ready) && <button type="button" onClick={stop} aria-label="Stop voiceover"><Square size={14} /> Stop</button>}
    <audio ref={audio} controls={ready} aria-label="Voiceover playback" onEnded={onEnded}
      onError={() => setError('Audio could not be played. Retry voiceover.')}
      style={{ display: ready ? 'block' : 'none', width: '100%', maxWidth: 360, height: 40 }} />
    {error && <p role="status" style={{ flexBasis: '100%', margin: 0, fontSize: '.8rem' }}>{error}</p>}
  </div>;
}
