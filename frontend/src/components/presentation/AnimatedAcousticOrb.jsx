import React, { useEffect, useRef } from 'react';

// Restores the original gyroscopic rings, shaded core and glass highlight.
export default function AnimatedAcousticOrb({ isPlaying = false, compact = false }) {
  const canvasRef = useRef(null);
  const animFrameIdRef = useRef(null);
  const rotationRef = useRef(0);
  const waveOffsetRef = useRef(0);
  // 5. Canvas Animation Rendering: Luxury Floating Acoustic Orb
  useEffect(() => {
    let active = true;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const render = () => {
      if (!active) return;
      if (document.hidden) {
        animFrameIdRef.current = requestAnimationFrame(render);
        return;
      }
      rotationRef.current += 0.015;
      waveOffsetRef.current += 0.04;

      // Playback-driven motion keeps visualization independent of the audio output path.
      const freqAmplitude = isPlaying ? 0.35 + Math.sin(waveOffsetRef.current * 3) * 0.18 : 0;

      // Draw Main Canvas
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;
        const cx = w / 2;
        const cy = h / 2;
        ctx.clearRect(0, 0, w, h);

        const orbRadius = 40;
        const pulseExpand = freqAmplitude * 20;

        // A. Dynamic Waveform Rings (Gyroscopic)
        const ringCount = 3;
        for (let r = 0; r < ringCount; r++) {
          const ringRadius = orbRadius + 14 + r * 10 + pulseExpand * (r + 1) * 0.5;
          const angleOffset = rotationRef.current * (r % 2 === 0 ? 1 : -0.8) + (r * Math.PI) / 3;
          
          ctx.save();
          ctx.translate(cx, cy);
          ctx.rotate(angleOffset);
          ctx.scale(1, 0.45 + r * 0.1);

          ctx.beginPath();
          // Draw undulating wave along the ellipse
          const segments = 60;
          for (let s = 0; s <= segments; s++) {
            const theta = (s / segments) * Math.PI * 2;
            const wave = Math.sin(theta * 6 + waveOffsetRef.current * 2) * (freqAmplitude * 6 + 1.5);
            const x = (ringRadius + wave) * Math.cos(theta);
            const y = (ringRadius + wave) * Math.sin(theta);
            if (s === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.closePath();

          ctx.lineWidth = 1.5 + freqAmplitude * 2;
          ctx.strokeStyle = r === 0 
            ? `rgba(56, 189, 248, ${0.4 + freqAmplitude * 0.6})` 
            : r === 1
            ? `rgba(245, 158, 11, ${0.35 + freqAmplitude * 0.55})`
            : `rgba(168, 85, 247, ${0.3 + freqAmplitude * 0.5})`;
          ctx.shadowBlur = 10 + freqAmplitude * 20;
          ctx.shadowColor = r === 0 ? "#38bdf8" : "#f59e0b";
          ctx.stroke();
          ctx.restore();
        }

        // B. Deep 3D Shaded Obsidian Core
        const coreGradient = ctx.createRadialGradient(
          cx - orbRadius * 0.35,
          cy - orbRadius * 0.35,
          orbRadius * 0.1,
          cx,
          cy,
          orbRadius
        );
        coreGradient.addColorStop(0, "#334155");
        coreGradient.addColorStop(0.35, "#1e293b");
        coreGradient.addColorStop(0.75, "#0f172a");
        coreGradient.addColorStop(1, "#020617");

        ctx.beginPath();
        ctx.arc(cx, cy, orbRadius, 0, Math.PI * 2);
        ctx.fillStyle = coreGradient;
        ctx.shadowBlur = 18 + freqAmplitude * 25;
        ctx.shadowColor = freqAmplitude > 0.1 ? "rgba(56, 189, 248, 0.7)" : "rgba(15, 23, 42, 0.8)";
        ctx.fill();

        // C. Equator Glow Trench
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(rotationRef.current * 0.5);
        ctx.scale(1, 0.28);
        ctx.beginPath();
        ctx.arc(0, 0, orbRadius * 0.98, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(56, 189, 248, ${0.4 + freqAmplitude * 0.6})`;
        ctx.lineWidth = 2 + freqAmplitude * 4;
        ctx.shadowBlur = 12 + freqAmplitude * 15;
        ctx.shadowColor = "#38bdf8";
        ctx.stroke();
        ctx.restore();

        // D. Specular Glass Highlight
        const specGrad = ctx.createRadialGradient(
          cx - orbRadius * 0.4,
          cy - orbRadius * 0.45,
          0,
          cx - orbRadius * 0.4,
          cy - orbRadius * 0.45,
          orbRadius * 0.45
        );
        specGrad.addColorStop(0, "rgba(255, 255, 255, 0.75)");
        specGrad.addColorStop(0.5, "rgba(255, 255, 255, 0.15)");
        specGrad.addColorStop(1, "transparent");

        ctx.beginPath();
        ctx.arc(cx - orbRadius * 0.4, cy - orbRadius * 0.45, orbRadius * 0.45, 0, Math.PI * 2);
        ctx.fillStyle = specGrad;
        ctx.shadowBlur = 0;
        ctx.fill();
      }

      if (!reducedMotion) animFrameIdRef.current = requestAnimationFrame(render);
    };

    render();
    return () => {
      active = false;
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
    };
  }, [isPlaying, compact]);

  return <canvas ref={canvasRef} width={280} height={160} aria-hidden="true"
    style={compact ? { width: 66, height: 38, flexShrink: 0 } : { maxWidth: '100%' }} />;
}
