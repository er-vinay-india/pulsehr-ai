"""Executive Presentation Slide Narration and Voiceover Engine for PulseHR AI.

Provides high-fidelity, studio-quality speech synthesis for presentation slides:
1. Normalizes slide `speaker_notes` and executive narratives into natural spoken English.
2. Synthesizes slide audio using executive neural voices (Andrew, Ryan, Ava, Brian).
3. Caches slide MP3 files and manifests on disk under exports/narration_{deck_id}.
4. Serves streaming audio for interactive web presentations (Orb presenter) and PowerPoint embedding.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import os
from pathlib import Path
import re
from typing import Any

from ...core import config
from ...db.database import get_connection

logger = logging.getLogger(__name__)

EXECUTIVE_VOICES = {
    "andrew": {
        "id": "en-US-AndrewMultilingualNeural",
        "name": "Andrew",
        "accent": "US Executive",
        "gender": "Male",
        "description": "Calm, deep, authoritative American corporate executive"
    },
    "ryan": {
        "id": "en-GB-RyanNeural",
        "name": "Ryan",
        "accent": "UK Global",
        "gender": "Male",
        "description": "Measured, BBC/documentary style global leadership"
    },
    "ava": {
        "id": "en-US-AvaNeural",
        "name": "Ava",
        "accent": "US Leadership",
        "gender": "Female",
        "description": "Poised, articulate strategic female executive"
    },
    "brian": {
        "id": "en-US-BrianNeural",
        "name": "Brian",
        "accent": "US Operations",
        "gender": "Male",
        "description": "Warm, articulate operational director"
    }
}

DEFAULT_VOICE_KEY = "andrew"


def clean_speaker_notes_for_speech(
    speaker_notes: str | None = None,
    slide_title: str = "",
    subtitle: str = "",
    narrative: str = ""
) -> str:
    """Converts structured speaker notes and slide narrative into smooth spoken narration."""
    raw = (speaker_notes or "").strip()
    if not raw or len(raw) < 15:
        # Fallback to narrative and title if notes are missing or trivial
        parts = [p for p in (slide_title, subtitle, narrative) if p and len(p.strip()) > 3]
        raw = ". ".join(parts)

    text = raw

    # Strip presenter prefixes like 'Presenter note: ', 'Speaker Note: '
    text = re.sub(r'^(?:presenter|speaker)\s*notes?:\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(?:presenter|speaker)\s*note:\s*', '', text, flags=re.IGNORECASE)

    # Remove markdown headers (### Header -> Header)
    text = re.sub(r'#+\s*', '', text)

    # Remove markdown bold/italics
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # Remove backtick code formatting
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Clean bullet points into flowing sentences
    text = re.sub(r'(?:^|\s+)[-*•]\s+', ' ', text)

    # Expand technical notations
    text = text.replace("±0.1%", "within zero point one percent")
    text = text.replace("±", "plus or minus ")
    text = text.replace("⚠️", "Attention: ")
    text = text.replace("vs.", "versus")
    text = text.replace("vs", "versus")
    text = text.replace("&", "and")

    # Clean percentages (e.g. "12.5%" -> "12.5 percent")
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 percent', text)

    # Clean currency (e.g. "$50k" -> "50 thousand dollars", "$100M" -> "100 million dollars")
    text = re.sub(r'\$(\d+(?:\.\d+)?)\s*[mM]\b', r'\1 million dollars', text)
    text = re.sub(r'\$(\d+(?:\.\d+)?)\s*[kK]\b', r'\1 thousand dollars', text)
    text = re.sub(r'\$(\d+(?:\.\d+)?)', r'\1 dollars', text)

    # Clean markdown links [label](url) -> label
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # Collapse multiple whitespaces and newlines into single spaces with punctuation
    text = re.sub(r'\n+', '. ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\.\s*\.', '.', text)

    return text.strip()


def get_narration_dir(deck_id: str) -> Path:
    """Returns the dedicated on-disk directory for a deck's audio files."""
    d = config.EXPORTS_DIR / f"narration_{deck_id}"
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _synthesize_text_to_mp3(text: str, voice_id: str, output_path: Path) -> None:
    """Synthesizes text to MP3 using edge-tts asynchronously."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice_id)
    await communicate.save(str(output_path))


def estimate_audio_duration_seconds(file_path: Path, word_count: int) -> float:
    """Estimates or reads duration in seconds of generated MP3 file."""
    if file_path.exists() and file_path.stat().st_size > 0:
        # Standard 64kbps or 128kbps MP3 bit rate: ~16,000 bytes per second for 128kbps, ~6000 for speech
        # edge-tts default speech rate is ~150 words per minute (2.5 words per second)
        return max(2.0, round(word_count / 2.5, 1))
    return max(2.0, round(word_count / 2.5, 1))


async def generate_deck_narration_async(
    deck_id: str,
    voice_key: str = DEFAULT_VOICE_KEY,
    conn=None
) -> dict[str, Any]:
    """Asynchronously generates MP3 narration files for every slide in a presentation deck."""
    voice_info = EXECUTIVE_VOICES.get(voice_key) or EXECUTIVE_VOICES[DEFAULT_VOICE_KEY]
    voice_id = voice_info["id"]

    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        row = conn.execute("SELECT id, title, spec_json FROM presentation_decks WHERE id=?", (deck_id,)).fetchone()
        if not row:
            raise ValueError(f"Presentation deck '{deck_id}' not found.")

        deck_spec = json.loads(row["spec_json"])
        slides = deck_spec.get("slides", [])
        if not slides:
            raise ValueError(f"Deck '{deck_id}' has no slides to narrate.")

        narration_dir = get_narration_dir(deck_id)
        manifest_path = narration_dir / "manifest.json"

        slide_manifests = []
        for slide in sorted(slides, key=lambda s: s.get("order", 1)):
            order = slide.get("order", 1)
            title = slide.get("title", f"Slide {order}")
            notes = slide.get("speaker_notes", "")
            narrative = slide.get("narrative", "")
            subtitle = slide.get("subtitle", "")

            spoken_text = clean_speaker_notes_for_speech(
                speaker_notes=notes,
                slide_title=title,
                subtitle=subtitle,
                narrative=narrative
            )
            mp3_filename = f"slide_{order}.mp3"
            mp3_path = narration_dir / mp3_filename

            # Synthesize audio if not already generated or if empty
            if not mp3_path.exists() or mp3_path.stat().st_size == 0:
                await _synthesize_text_to_mp3(spoken_text, voice_id, mp3_path)

            file_size = mp3_path.stat().st_size if mp3_path.exists() else 0
            word_count = len(spoken_text.split())
            duration = estimate_audio_duration_seconds(mp3_path, word_count)

            slide_manifests.append({
                "order": order,
                "title": title,
                "audio_filename": mp3_filename,
                "audio_url": f"/api/presentations/{deck_id}/narration/slide/{order}",
                "transcript": spoken_text,
                "word_count": word_count,
                "duration_seconds": duration,
                "file_size_bytes": file_size
            })

        total_duration = round(sum(s["duration_seconds"] for s in slide_manifests), 1)

        manifest = {
            "deck_id": deck_id,
            "deck_title": deck_spec.get("metadata", {}).get("title") or row["title"],
            "voice": voice_info,
            "slide_count": len(slide_manifests),
            "total_duration_seconds": total_duration,
            "slides": slide_manifests,
            "status": "ready"
        }

        # Save manifest to disk
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return manifest

    finally:
        if should_close:
            conn.close()


def get_deck_narration_manifest(deck_id: str) -> dict[str, Any] | None:
    """Reads existing narration manifest from disk if available."""
    manifest_path = get_narration_dir(deck_id) / "manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Could not read manifest at {manifest_path}: {exc}")
    return None
