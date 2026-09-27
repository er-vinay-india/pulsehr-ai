import React, { useEffect, useRef } from "react";

/**
 * AnimatedAcousticOrb (HRIDAY Intelligent Human Heart Engine)
 *
 * Renders an anatomically realistic human heart (aorta with 3 trunk branches,
 * pulmonary artery, superior vena cava, muscular atria and ventricles, tapered apex,
 * and branching vascular tree) in the finalized HRIDAY warm intelligence palette
 * (Deep Navy #102A43, Human Teal #0F766E, Warm Cyan #0891B2, Heart Green #3F7D20,
 * and subtle Warm Gold #B7791F accents).
 *
 * Implements realistic dual-stroke (systole-diastole / lub-dub) biomechanical heartbeat
 * pulsation, synchronized with acoustic voice waveforms when isPlaying is active.
 */
export default function AnimatedAcousticOrb({ isPlaying = false, compact = false }) {
  const canvasRef = useRef(null);
  const animFrameIdRef = useRef(null);
  const waveOffsetRef = useRef(0);

  useEffect(() => {
    let active = true;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const render = () => {
      if (!active) return;
      if (document.hidden) {
        animFrameIdRef.current = requestAnimationFrame(render);
        return;
      }

      waveOffsetRef.current += isPlaying ? 0.08 : 0.035;

      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        const w = canvas.width;
        const h = canvas.height;
        const cx = w / 2;
        const cy = h / 2 + (compact ? 1 : 2);
        ctx.clearRect(0, 0, w, h);

        // 1. Dual-Stroke (Systole - Diastole) Biomechanical Heartbeat Rhythm
        const heartPeriod = isPlaying ? 780 : 1100;
        const t = (Date.now() % heartPeriod) / heartPeriod;
        let heartPulse = 0;
        if (t < 0.16) {
          // S1: Primary Ventricular Systole (deep contraction/surge)
          heartPulse = Math.sin((t / 0.16) * Math.PI) * (isPlaying ? 0.18 : 0.10);
        } else if (t >= 0.22 && t < 0.38) {
          // S2: Secondary Atrial Recoil (softer rebound)
          heartPulse = Math.sin(((t - 0.22) / 0.16) * Math.PI) * (isPlaying ? 0.09 : 0.05);
        }

        const currentScale = (compact ? 0.88 : 1.15) * (1 + heartPulse);
        const speechAmp = isPlaying ? 0.4 + Math.sin(waveOffsetRef.current * 4) * 0.25 : 0;

        // 2. Surrounding Acoustic Waveform Rings (Teal / Warm Cyan)
        const ringCount = compact ? 2 : 3;
        for (let r = 0; r < ringCount; r++) {
          const ringRadius = (compact ? 24 : 44) + r * (compact ? 7 : 12) + speechAmp * 15 * (r + 1);
          ctx.save();
          ctx.translate(cx, cy);
          ctx.rotate(waveOffsetRef.current * (r % 2 === 0 ? 0.4 : -0.3) + (r * Math.PI) / 3);
          ctx.scale(1, 0.55);

          ctx.beginPath();
          const segments = 48;
          for (let s = 0; s <= segments; s++) {
            const theta = (s / segments) * Math.PI * 2;
            const wave = Math.sin(theta * 5 + waveOffsetRef.current * 2) * (speechAmp * 4 + 1.2);
            const x = (ringRadius + wave) * Math.cos(theta);
            const y = (ringRadius + wave) * Math.sin(theta);
            if (s === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          }
          ctx.closePath();

          ctx.lineWidth = compact ? 1 : 1.5 + speechAmp * 1.5;
          ctx.strokeStyle =
            r === 0
              ? `rgba(8, 145, 178, ${0.45 + speechAmp * 0.45})`
              : r === 1
              ? `rgba(15, 118, 110, ${0.3 + speechAmp * 0.35})`
              : `rgba(16, 42, 67, ${0.25 + speechAmp * 0.3})`;
          ctx.shadowBlur = compact ? 6 : 14 + speechAmp * 15;
          ctx.shadowColor = "#0891B2";
          ctx.stroke();
          ctx.restore();
        }

        ctx.save();
        ctx.translate(cx, cy);
        ctx.scale(currentScale, currentScale);

        // 3. Great Vessels: Aortic Arch, Pulmonary Trunk & Superior Vena Cava
        // A. Superior Vena Cava (Right superior vertical venous trunk)
        const svcGrad = ctx.createLinearGradient(12, -30, 24, -30);
        svcGrad.addColorStop(0, "#102A43");
        svcGrad.addColorStop(0.5, "#123B5D");
        svcGrad.addColorStop(1, "#0B1F3A");
        ctx.fillStyle = svcGrad;
        ctx.beginPath();
        ctx.moveTo(13, -20);
        ctx.lineTo(15, -42);
        ctx.bezierCurveTo(15, -45, 23, -45, 23, -42);
        ctx.lineTo(21, -16);
        ctx.closePath();
        ctx.fill();

        // B. Aortic Arch (Arteria Aorta with 3 branching arterial trunks)
        const aortaGrad = ctx.createLinearGradient(-15, -48, 10, -18);
        aortaGrad.addColorStop(0, "#0891B2");
        aortaGrad.addColorStop(0.4, "#0F766E");
        aortaGrad.addColorStop(0.8, "#14B8A6");
        aortaGrad.addColorStop(1, "#102A43");

        ctx.fillStyle = aortaGrad;
        ctx.shadowBlur = 10 + speechAmp * 12;
        ctx.shadowColor = "rgba(15, 118, 110, 0.6)";

        ctx.beginPath();
        // Aortic Arch main curvature
        ctx.moveTo(-6, -18);
        ctx.bezierCurveTo(-6, -34, 4, -48, 14, -48);
        ctx.bezierCurveTo(24, -48, 24, -36, 17, -24);
        ctx.bezierCurveTo(12, -18, 5, -14, 0, -12);
        ctx.closePath();
        ctx.fill();

        // 3 Arterial Branches off the Aortic Arch (with subtle warm gold touch)
        ctx.lineWidth = compact ? 2 : 2.8;
        ctx.strokeStyle = "#22C7F2";
        ctx.lineCap = "round";

        // Branch 1: Brachiocephalic
        ctx.beginPath();
        ctx.moveTo(5, -46);
        ctx.lineTo(3, -56);
        ctx.stroke();

        // Branch 2: Left Common Carotid (Warm Gold Accent)
        ctx.strokeStyle = "#B7791F";
        ctx.beginPath();
        ctx.moveTo(11, -48);
        ctx.lineTo(12, -58);
        ctx.stroke();

        // Branch 3: Left Subclavian
        ctx.strokeStyle = "#22C7F2";
        ctx.beginPath();
        ctx.moveTo(17, -46);
        ctx.lineTo(20, -56);
        ctx.stroke();

        // C. Pulmonary Trunk (crossing anterior to aorta)
        const pulmGrad = ctx.createLinearGradient(-18, -25, -2, -12);
        pulmGrad.addColorStop(0, "#102A43");
        pulmGrad.addColorStop(0.6, "#0F766E");
        pulmGrad.addColorStop(1, "#0891B2");
        ctx.fillStyle = pulmGrad;
        ctx.beginPath();
        ctx.moveTo(-16, -16);
        ctx.bezierCurveTo(-22, -26, -12, -34, -2, -26);
        ctx.bezierCurveTo(-4, -18, -10, -14, -16, -16);
        ctx.closePath();
        ctx.fill();

        // 4. Anatomical Human Heart Body (Myocardium & Ventricles)
        // Realistic asymmetrical shape rendered in HRIDAY Human Teal & Deep Navy
        const heartBodyGrad = ctx.createRadialGradient(-8, -4, 4, -4, 6, 48);
        heartBodyGrad.addColorStop(0, "#0891B2"); // Anterior Warm Cyan glow
        heartBodyGrad.addColorStop(0.35, "#0F766E"); // Human Teal muscle wall
        heartBodyGrad.addColorStop(0.7, "#3F7D20"); // Heart Green subtle resonance
        heartBodyGrad.addColorStop(1, "#102A43"); // Deep Navy foundation

        ctx.fillStyle = heartBodyGrad;
        ctx.shadowBlur = 18 + speechAmp * 18;
        ctx.shadowColor = isPlaying ? "rgba(8, 145, 178, 0.85)" : "rgba(15, 118, 110, 0.65)";

        ctx.beginPath();
        // Base of heart (under great vessels)
        ctx.moveTo(-6, -16);
        // Right Atrium superior border & auricle
        ctx.bezierCurveTo(4, -18, 16, -20, 26, -12);
        // Right Atrium lateral curve
        ctx.bezierCurveTo(34, -4, 33, 8, 26, 18);
        // Right Ventricle descending curve
        ctx.bezierCurveTo(20, 28, 12, 36, 0, 44);
        // Cardiac Apex (tilted to bottom-left anatomically at ~ -12, 48)
        ctx.bezierCurveTo(-8, 49, -15, 48, -17, 43);
        // Left Ventricle ascending lateral muscular wall
        ctx.bezierCurveTo(-26, 32, -36, 18, -36, 0);
        // Left Atrium / Auricle notch
        ctx.bezierCurveTo(-36, -12, -24, -16, -14, -15);
        ctx.closePath();
        ctx.fill();

        // 5. Anterior Interventricular Sulcus & Vascular Network (Soft Aqua & Warm Gold)
        ctx.shadowBlur = 0;
        ctx.lineCap = "round";

        // Main Coronary Sulcus (Diagonal branch heading toward apex)
        ctx.strokeStyle = "rgba(232, 247, 245, 0.9)";
        ctx.lineWidth = compact ? 1.2 : 1.8;
        ctx.beginPath();
        ctx.moveTo(-5, -12);
        ctx.bezierCurveTo(-3, 6, -6, 20, -14, 42);
        ctx.stroke();

        // Branching Capillaries
        ctx.strokeStyle = "rgba(183, 121, 31, 0.65)"; // Warm Gold personality touch
        ctx.lineWidth = compact ? 0.8 : 1.1;

        // Right ventricular branch 1
        ctx.beginPath();
        ctx.moveTo(-4, 4);
        ctx.bezierCurveTo(4, 8, 12, 12, 16, 20);
        ctx.stroke();

        // Right ventricular branch 2
        ctx.strokeStyle = "rgba(232, 247, 245, 0.7)";
        ctx.beginPath();
        ctx.moveTo(-6, 18);
        ctx.bezierCurveTo(0, 24, 6, 28, 8, 34);
        ctx.stroke();

        // Left ventricular branch 1
        ctx.beginPath();
        ctx.moveTo(-4, 0);
        ctx.bezierCurveTo(-12, 4, -20, 8, -26, 14);
        ctx.stroke();

        // Left ventricular branch 2
        ctx.strokeStyle = "rgba(183, 121, 31, 0.6)"; // Warm Gold
        ctx.beginPath();
        ctx.moveTo(-8, 16);
        ctx.bezierCurveTo(-16, 22, -22, 26, -24, 32);
        ctx.stroke();

        // 6. Volumetric Muscular Specular Highlight (3D Curved Sheen in Soft Aqua)
        const sheenGrad = ctx.createLinearGradient(-30, -10, -5, 25);
        sheenGrad.addColorStop(0, "rgba(255, 255, 255, 0.55)");
        sheenGrad.addColorStop(0.4, "rgba(232, 247, 245, 0.25)");
        sheenGrad.addColorStop(1, "transparent");

        ctx.fillStyle = sheenGrad;
        ctx.beginPath();
        ctx.moveTo(-28, -2);
        ctx.bezierCurveTo(-30, 10, -22, 26, -14, 36);
        ctx.bezierCurveTo(-16, 26, -22, 12, -20, 0);
        ctx.closePath();
        ctx.fill();

        ctx.restore();
      }

      if (!reducedMotion) animFrameIdRef.current = requestAnimationFrame(render);
    };

    render();
    return () => {
      active = false;
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
    };
  }, [isPlaying, compact]);

  return (
    <canvas
      ref={canvasRef}
      width={280}
      height={180}
      aria-label="HRIDAY Warm Human Intelligence Acoustic Engine"
      style={compact ? { width: 72, height: 46, flexShrink: 0 } : { maxWidth: "100%", height: "auto" }}
    />
  );
}
