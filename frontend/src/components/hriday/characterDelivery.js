const segmenter = new Intl.Segmenter(undefined, { granularity: 'grapheme' });

// Pace already-sanitized text independently of network chunk sizes. A grapheme
// keeps emoji and combining characters intact. Reveal one character per tick,
// even when an entire answer arrives in a single network burst.
export class CharacterDelivery {
  constructor(onText, {
    schedule = (callback, delay) => setTimeout(callback, delay),
    cancel = timer => clearTimeout(timer),
    instant = () => globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true,
    intervalMs = 35,
  } = {}) {
    this.onText = onText;
    this.schedule = schedule;
    this.cancel = cancel;
    this.instant = instant;
    this.intervalMs = intervalMs;
    this.visible = '';
    this.characters = [];
    this.index = 0;
    this.timer = null;
    this.onDrain = null;
    this.revision = 0;
    this.stopped = false;
  }

  setText(text) {
    this.characters = Array.from(segmenter.segment(text), part => part.segment);
    // Final validation may replace previously streamed text. Discard the old
    // prefix immediately rather than animating from a rejected answer.
    let prefix = '';
    this.index = 0;
    if (text.startsWith(this.visible)) {
      while (this.index < this.characters.length
        && prefix.length + this.characters[this.index].length <= this.visible.length) {
        prefix += this.characters[this.index++];
      }
    }
    this.show(prefix);
    this.pump();
  }

  show(text) {
    if (text === this.visible) return;
    this.visible = text;
    this.onText(text);
  }

  pump() {
    if (this.stopped) return;
    if (this.instant()) {
      this.clearTimer();
      this.index = this.characters.length;
      this.show(this.characters.join(''));
    }
    if (this.index === this.characters.length) {
      this.clearTimer();
      const drained = this.onDrain;
      this.onDrain = null;
      drained?.();
      return;
    }
    if (this.timer !== null) return;
    const revision = this.revision;
    this.timer = this.schedule(() => {
      if (revision !== this.revision) return;
      this.timer = null;
      const next = this.index + 1;
      this.show(this.visible + this.characters.slice(this.index, next).join(''));
      this.index = next;
      this.pump();
    }, this.intervalMs);
  }

  finish(onDrain) {
    this.onDrain = onDrain;
    this.pump();
  }

  clearTimer() {
    this.revision += 1;
    if (this.timer !== null) this.cancel(this.timer);
    this.timer = null;
  }

  reset() {
    this.clearTimer();
    this.onDrain = null;
    this.characters = [];
    this.index = 0;
    this.show('');
  }

  stop() {
    this.stopped = true;
    this.clearTimer();
    this.onDrain = null;
  }
}
