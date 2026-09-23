import io
import wave
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services import local_voiceover


def wav_bytes(frames=40):
    output = io.BytesIO()
    with wave.open(output, 'wb') as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(22050)
        sound.writeframes(b'\0\0' * frames)
    return output.getvalue()


def test_voiceover_validates_and_streams(monkeypatch):
    monkeypatch.setattr(local_voiceover, 'synthesize_local', lambda text: wav_bytes())
    client = TestClient(app)
    route = '/api/analytics/decision-brief/voiceover'
    response = client.post(route, json={'text': 'Revenue increased by 12 percent.'})
    assert response.status_code == 200
    assert response.headers['content-type'] == 'audio/wav'
    assert response.content == wav_bytes()
    for text in ('', ' ', 'x' * 12001):
        assert client.post(route, json={'text': text}).status_code == 422


def test_voiceover_engine_unavailable(monkeypatch):
    monkeypatch.setattr(local_voiceover.shutil, 'which', lambda _: None)
    assert TestClient(app).post('/api/analytics/decision-brief/voiceover', json={'text': 'Read this.'}).status_code == 503


def test_synthesis_rejects_header_only_and_removes_temporary_files(monkeypatch):
    monkeypatch.setattr(local_voiceover.shutil, 'which', lambda _: '/usr/bin/say')
    paths = []
    def run(args, **kwargs):
        path = Path(args[args.index('-o') + 1])
        paths.append(path)
        path.write_bytes(wav_bytes(0))
    monkeypatch.setattr(local_voiceover.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='empty audio'):
        local_voiceover.synthesize_local('Check empty speech.')
    assert not paths[0].exists()
