import wave
from types import SimpleNamespace

import pytest

from vietsub.asr import (choose_default_model, format_srt_time, segments_to_cues, transcribe,
                         wav_duration)
from vietsub.models import Cue
from vietsub.parser import parse_srt
from vietsub.writer import write_bilingual_srt, write_srt


def seg(start, end, text):
    return SimpleNamespace(start=start, end=end, text=text)


@pytest.mark.parametrize("sec,expected", [
    (0, "00:00:00,000"), (1.5, "00:00:01,500"), (61.0004, "00:01:01,000"),
    (3599.9996, "01:00:00,000"), (3725.123, "01:02:05,123"), (-2, "00:00:00,000"),
    (0.0015, "00:00:00,002"),
])
def test_format_srt_time(sec, expected):
    assert format_srt_time(sec) == expected


def test_segments_to_cues_japanese_roundtrip():
    cues = segments_to_cues([seg(0.0, 2.2, " こんにちは、皆さん。"), seg(2.5, 5.0, "  "),
                             seg(5.1, 5.1, "カタカナと漢字")])
    assert [c.text for c in cues] == ["こんにちは、皆さん。", "カタカナと漢字"]
    assert [c.index for c in cues] == [1, 2]
    assert cues[1].start == "00:00:05,100" and cues[1].end == "00:00:05,400"
    assert parse_srt(write_srt(cues))[0] == cues


def test_segments_empty():
    assert segments_to_cues([]) == []
    assert write_srt(segments_to_cues([])) == ""


class FakeModel:
    def __init__(self, segs, duration):
        self.segs, self.duration, self.kwargs = segs, duration, None

    def transcribe(self, path, **kwargs):
        self.kwargs = kwargs
        return iter(self.segs), SimpleNamespace(duration=self.duration)


def test_transcribe_with_mock_progress():
    m = FakeModel([seg(0, 1.5, "おはよう"), seg(2, 3.0, "ございます")], 3.0)
    calls = []
    cues, dur = transcribe(m, "x.wav", progress=lambda *a: calls.append(a))
    assert dur == 3.0
    assert [c.text for c in cues] == ["おはよう", "ございます"]
    assert calls == [(1, 1.5, 3.0, "おはよう"), (2, 3.0, 3.0, "ございます")]
    assert m.kwargs["language"] == "ja" and m.kwargs["vad_filter"] is True


def test_transcribe_empty_audio(tmp_path):
    p = tmp_path / "silence.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000)
    assert wav_duration(str(p)) == pytest.approx(1.0)
    cues, dur = transcribe(FakeModel([], 1.0), str(p))
    assert cues == [] and dur == 1.0


def test_choose_default_model():
    assert choose_default_model(None) == "tiny"
    assert choose_default_model(800) == "tiny"
    assert choose_default_model(2700) == "base"


def test_bilingual_srt():
    ja = [Cue(1, "00:00:01,000", "00:00:02,000", "猫です")]
    vi = [Cue(1, "00:00:01,000", "00:00:02,000", "Đây là con mèo")]
    out = write_bilingual_srt(ja, vi)
    assert out == "1\n00:00:01,000 --> 00:00:02,000\n猫です\nĐây là con mèo\n"
    with pytest.raises(ValueError):
        write_bilingual_srt(ja, [])


@pytest.mark.skipif(__import__("shutil").which("ffmpeg") is None, reason="ffmpeg not installed")
def test_extract_audio_from_real_mp4(tmp_path):
    import subprocess
    from vietsub.asr import extract_audio
    mp4 = tmp_path / "t.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-f", "lavfi", "-i", "color=c=black:s=64x64:d=2", "-shortest", "-c:v", "libx264",
                    "-c:a", "aac", str(mp4)], check=True)
    wav = extract_audio(str(mp4), str(tmp_path / "a.wav"))
    with wave.open(wav, "rb") as w:
        assert w.getframerate() == 16000 and w.getnchannels() == 1
    assert wav_duration(wav) == pytest.approx(2.0, abs=0.1)


def test_load_wav_values(tmp_path):
    import numpy as np
    from vietsub.asr import load_wav
    p = tmp_path / "v.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(np.array([0, 16384, -32768], dtype="<i2").tobytes())
    assert load_wav(str(p)).tolist() == [0.0, 0.5, -1.0]


def test_transcribe_zero_length_wav(tmp_path):
    p = tmp_path / "empty.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    model = FakeModel([seg(0, 1, "should not be called")], 0)
    assert transcribe(model, str(p)) == ([], 0.0)
    assert model.kwargs is None
