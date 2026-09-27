/**
 * hridayVoice.js
 *
 * Spoken audio introduction and voice management for HRIDAY:
 * Human Reasoning Intelligence, Dedicated to Assisting You.
 */

export const HRIDAY_ACRONYM = "Human Reasoning Intelligence, Dedicated to Assisting You";
export const HRIDAY_MOTTO = "Think. Act. Achieve Together.";

export const HRIDAY_INTRO_SCRIPT =
  "Hi, I’m HRIDAY — Human Reasoning Intelligence, Dedicated to Assisting You. I’m here to make your work a little easier, help you find clarity when things get complex, and support you whenever you need it. Think. Act. Achieve Together.";

/**
 * Plays HRIDAY's spoken voice introduction via Web Speech API with backend audio fallback.
 * @param {Function} onStart - Called when voice begins speaking
 * @param {Function} onEnd - Called when voice completes or stops
 * @returns {Function} stopFunction - Call to immediately stop voiceover
 */
export function speakHridayIntro(onStart = () => {}, onEnd = () => {}) {
  let activeAudio = null;

  // 1. Primary: Browser Web Speech Synthesis
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(HRIDAY_INTRO_SCRIPT);
      utterance.rate = 0.98;
      utterance.pitch = 1.0;

      // Select natural sounding voice if available
      const voices = window.speechSynthesis.getVoices();
      const naturalVoice = voices.find(
        (v) =>
          v.lang.startsWith("en") &&
          (v.name.includes("Natural") ||
            v.name.includes("Samantha") ||
            v.name.includes("Google") ||
            v.name.includes("Daniel") ||
            v.name.includes("Alex"))
      );
      if (naturalVoice) utterance.voice = naturalVoice;

      utterance.onstart = () => onStart(true);
      utterance.onend = () => onEnd(false);
      utterance.onerror = () => onEnd(false);

      window.speechSynthesis.speak(utterance);
      return () => {
        try {
          window.speechSynthesis.cancel();
        } catch {}
        onEnd(false);
      };
    } catch (e) {
      console.debug("Web Speech Synthesis failed, trying backend TTS fallback:", e);
    }
  }

  // 2. Secondary: Backend voiceover endpoint fallback
  try {
    const audio = new Audio();
    activeAudio = audio;
    fetch("/api/analytics/decision-brief/voiceover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: HRIDAY_INTRO_SCRIPT }),
    })
      .then((res) => (res.ok ? res.blob() : null))
      .then((blob) => {
        if (!blob) {
          onEnd(false);
          return;
        }
        const url = URL.createObjectURL(blob);
        audio.src = url;
        audio.onplay = () => onStart(true);
        audio.onended = () => {
          URL.revokeObjectURL(url);
          onEnd(false);
        };
        audio.onerror = () => onEnd(false);
        audio.play().catch(() => onEnd(false));
      })
      .catch(() => onEnd(false));

    return () => {
      if (activeAudio) {
        activeAudio.pause();
        activeAudio = null;
      }
      onEnd(false);
    };
  } catch {
    onEnd(false);
    return () => {};
  }
}
