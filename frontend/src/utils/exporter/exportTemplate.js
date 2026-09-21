/**
 * Full HTML document wrapper template with embedded CSS and presentation controller.
 */

import { escapeHtml } from "./exportFormatter";

export function generateFullPresentationHtml(title, slidesHtml, totalSlides, currentTheme) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)} · Frontend Slides</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=Fraunces:ital,opsz,wght@0,9..144,400..900;1,9..144,400..900&family=Manrope:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&family=Space+Mono:wght@400;700&family=Syne:wght@600;700;800&display=swap" rel="stylesheet">
  <style>
    /* ===========================================
       FRONTEND SLIDES: FIXED 16:9 STAGE ARCHITECTURE
       Based on zarazhangrui/frontend-slides
       =========================================== */
    :root {
      --stage-bg: ${currentTheme.stage_bg};
      --slide-bg: ${currentTheme.slide_bg};
      --accent-color: ${currentTheme.accent_color};
      --font-display: ${currentTheme.font_display};
      --font-body: ${currentTheme.font_body};
    }

    * { box-sizing: border-box; }

    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      padding: 0;
      overflow: hidden;
      background: var(--stage-bg);
      font-family: var(--font-body);
      -webkit-font-smoothing: antialiased;
    }

    .deck-viewport {
      position: fixed;
      inset: 0;
      overflow: hidden;
      background: var(--stage-bg);
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .deck-stage {
      position: absolute;
      left: 0;
      top: 0;
      width: 1920px;
      height: 1080px;
      overflow: hidden;
      transform-origin: 0 0;
      background: var(--slide-bg);
      box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.8);
      user-select: text;
    }

    .slide {
      position: absolute;
      inset: 0;
      width: 1920px;
      height: 1080px;
      overflow: hidden;
      display: block;
      visibility: hidden;
      opacity: 0;
      pointer-events: none;
      background: var(--slide-bg);
      transition: opacity 0.25s ease, visibility 0.25s ease;
    }

    .slide.active,
    .slide.visible {
      visibility: visible;
      opacity: 1;
      pointer-events: auto;
      z-index: 1;
    }

    /* Floating Controls */
    .deck-controls {
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      align-items: center;
      gap: 12px;
      background: rgba(15, 23, 42, 0.9);
      backdrop-filter: blur(16px);
      padding: 8px 18px;
      border-radius: 9999px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
      z-index: 1000;
      user-select: none;
    }

    .deck-controls button {
      background: rgba(255, 255, 255, 0.08);
      border: none;
      color: #fff;
      padding: 6px 14px;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }

    .deck-controls button:hover:not(:disabled) {
      background: var(--accent-color);
      color: #fff;
      transform: scale(1.04);
    }

    .deck-controls button:disabled {
      opacity: 0.3;
      cursor: not-allowed;
    }

    .slide-counter {
      color: #94a3b8;
      font-size: 13px;
      font-weight: 600;
      padding: 0 4px;
    }

    .progress-bar {
      position: fixed;
      bottom: 0;
      left: 0;
      height: 3px;
      background: var(--accent-color);
      transition: width 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      z-index: 999;
    }

    /* Print & PDF */
    @media print {
      html, body {
        width: 1920px !important;
        height: auto !important;
        overflow: visible !important;
        background: #fff !important;
      }
      .deck-viewport { position: static !important; }
      .deck-stage {
        position: static !important;
        transform: none !important;
        box-shadow: none !important;
      }
      .slide {
        position: relative !important;
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        break-after: page !important;
        page-break-after: always !important;
      }
      .deck-controls, .progress-bar { display: none !important; }
    }
  </style>
</head>
<body>
  <div class="deck-viewport">
    <div class="deck-stage" id="deckStage">
      ${slidesHtml}
    </div>
  </div>

  <div class="deck-controls">
    <button id="prevBtn" title="Previous (Left Arrow / Page Up)">&larr; Prev</button>
    <div class="slide-counter" id="slideCounter">1 / ${totalSlides}</div>
    <button id="nextBtn" title="Next (Right Arrow / Space / Page Down)">Next &rarr;</button>
    <button id="fsBtn" title="Fullscreen (F)">Fullscreen</button>
  </div>

  <div class="progress-bar" id="progressBar" style="width: ${(1 / totalSlides) * 100}%;"></div>

  <script>
    class SlidePresentation {
      constructor() {
        this.slides = Array.from(document.querySelectorAll('.slide'));
        this.currentSlide = 0;
        this.totalSlides = this.slides.length;
        this.stage = document.getElementById('deckStage');
        this.prevBtn = document.getElementById('prevBtn');
        this.nextBtn = document.getElementById('nextBtn');
        this.fsBtn = document.getElementById('fsBtn');
        this.counter = document.getElementById('slideCounter');
        this.progressBar = document.getElementById('progressBar');

        this.setupStageScale();
        this.setupKeyboardNav();
        this.setupTouchNav();
        this.setupButtons();
        this.showSlide(0);
      }

      setupStageScale() {
        const scale = () => {
          const factor = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
          const x = (window.innerWidth - 1920 * factor) / 2;
          const y = (window.innerHeight - 1080 * factor) / 2;
          this.stage.style.transform = "translate(" + x + "px, " + y + "px) scale(" + factor + ")";
        };
        scale();
        window.addEventListener('resize', scale);
      }

      setupKeyboardNav() {
        window.addEventListener('keydown', (e) => {
          if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable)) return;
          if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {
            e.preventDefault();
            this.showSlide(this.currentSlide + 1);
          } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
            e.preventDefault();
            this.showSlide(this.currentSlide - 1);
          } else if (e.key === 'Home') {
            e.preventDefault();
            this.showSlide(0);
          } else if (e.key === 'End') {
            e.preventDefault();
            this.showSlide(this.totalSlides - 1);
          } else if (e.key === 'f' || e.key === 'F') {
            e.preventDefault();
            this.toggleFullscreen();
          }
        });
      }

      setupTouchNav() {
        let startX = 0;
        window.addEventListener('touchstart', (e) => {
          if (e.touches && e.touches[0]) startX = e.touches[0].clientX;
        }, { passive: true });

        window.addEventListener('touchend', (e) => {
          if (!e.changedTouches || !e.changedTouches[0]) return;
          const diffX = startX - e.changedTouches[0].clientX;
          if (Math.abs(diffX) > 44) {
            if (diffX > 0) this.showSlide(this.currentSlide + 1);
            else this.showSlide(this.currentSlide - 1);
          }
        }, { passive: true });
      }

      setupButtons() {
        this.prevBtn.addEventListener('click', () => this.showSlide(this.currentSlide - 1));
        this.nextBtn.addEventListener('click', () => this.showSlide(this.currentSlide + 1));
        this.fsBtn.addEventListener('click', () => this.toggleFullscreen());
      }

      toggleFullscreen() {
        if (!document.fullscreenElement) {
          document.documentElement.requestFullscreen().catch(() => {});
        } else {
          document.exitFullscreen().catch(() => {});
        }
      }

      showSlide(index) {
        this.currentSlide = Math.max(0, Math.min(index, this.totalSlides - 1));
        this.slides.forEach((slide, i) => {
          slide.classList.toggle('active', i === this.currentSlide);
          slide.classList.toggle('visible', i === this.currentSlide);
        });

        this.counter.textContent = (this.currentSlide + 1) + " / " + this.totalSlides;
        this.prevBtn.disabled = this.currentSlide <= 0;
        this.nextBtn.disabled = this.currentSlide >= this.totalSlides - 1;
        this.progressBar.style.width = (((this.currentSlide + 1) / this.totalSlides) * 100) + "%";
      }
    }

    window.addEventListener('DOMContentLoaded', () => {
      new SlidePresentation();
    });
  </script>
</body>
</html>`;
}
