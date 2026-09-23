"""Local speech synthesis; briefing text never leaves this server."""
import io
import wave
import shutil
import subprocess
import tempfile
from pathlib import Path


def synthesize_local(text: str) -> bytes:
    engine = shutil.which('say')
    if not engine:
        raise RuntimeError('Local voiceover requires the macOS speech engine on this server.')
    with tempfile.TemporaryDirectory(prefix='pulsehr-voice-') as directory:
        source = Path(directory) / 'speech.txt'
        output = Path(directory) / 'speech.wav'
        source.write_text(text, encoding='utf-8')
        subprocess.run([engine, '-f', str(source), '-o', str(output),
                        '--data-format=LEI16@22050'], check=True, timeout=90,
                       capture_output=True)
        audio = output.read_bytes()
        with wave.open(io.BytesIO(audio)) as recording:
            frames = recording.getnframes()
        if frames == 0:
            raise RuntimeError('The local speech engine returned empty audio.')
        return audio
