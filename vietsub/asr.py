"""Japanese speech recognition: video -> audio -> faster-whisper segments -> Cue list."""
import os
import shutil
import subprocess
from typing import Any, Callable, Iterable, List, Optional, Tuple

from .models import Cue

SAMPLE_RATE = 16000
MODEL_SIZES = ("tiny", "base")
# Approximate resident RAM (MB) of the int8 CPU model while transcribing.
MODEL_RAM_MB = {"tiny": 350, "base": 550}


def format_srt_time(seconds: float) -> str:
    """Seconds -> 'HH:MM:SS,mmm' (negatives clamped to 0, rounded to ms)."""
    total_ms = max(0, int(round(float(seconds) * 1000)))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_cues(segments: Iterable[Any], min_duration: float = 0.3) -> List[Cue]:
    """Convert objects with .start/.end/.text (seconds) to numbered Cues, skipping empty text."""
    cues: List[Cue] = []
    for seg in segments:
        text = (getattr(seg, "text", "") or "").strip()
        if not text:
            continue
        start = float(seg.start)
        end = max(float(seg.end), start + min_duration)
        cues.append(Cue(len(cues) + 1, format_srt_time(start), format_srt_time(end), text))
    return cues


def available_ram_mb() -> Optional[int]:
    """MemAvailable from /proc/meminfo (or cgroup limit if smaller); None if unknown."""
    avail = None
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    avail = int(line.split()[1]) // 1024
    except OSError:
        return None
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
            if raw.isdigit():
                limit = int(raw) // (1024 * 1024)
                if limit < 10_000_000:
                    avail = min(avail, limit) if avail is not None else limit
        except OSError:
            continue
    return avail


def choose_default_model(avail_mb: Optional[int]) -> str:
    """'base' when there is comfortable headroom (>= 1200 MB available), else 'tiny'."""
    if avail_mb is None:
        return "tiny"
    return "base" if avail_mb >= 1200 else "tiny"


def extract_audio(video_path: str, wav_path: str, ffmpeg: Optional[str] = None) -> str:
    """Extract 16 kHz mono PCM WAV with ffmpeg; falls back to PyAV if ffmpeg is missing."""
    ffmpeg = ffmpeg or shutil.which("ffmpeg")
    if ffmpeg:
        cmd = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", video_path,
               "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", wav_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()[:500]}")
        return wav_path
    return _extract_with_pyav(video_path, wav_path)


def _extract_with_pyav(video_path: str, wav_path: str) -> str:
    import wave

    import numpy as np
    from faster_whisper.audio import decode_audio

    audio = decode_audio(video_path, sampling_rate=SAMPLE_RATE)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return wav_path


def wav_duration(wav_path: str) -> float:
    import wave
    with wave.open(wav_path, "rb") as w:
        return w.getnframes() / float(w.getframerate() or 1)


def load_wav(wav_path: str):
    """Read a 16-bit PCM mono WAV into float32 numpy array in [-1, 1] (no PyAV needed)."""
    import wave

    import numpy as np
    with wave.open(wav_path, "rb") as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1 or w.getframerate() != SAMPLE_RATE:
            raise ValueError("expected 16 kHz mono 16-bit WAV (use extract_audio)")
        frames = w.readframes(w.getnframes())
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0


def load_model(size: str = "base", cpu_threads: int = 0) -> Any:
    if size not in MODEL_SIZES:
        raise ValueError(f"model size must be one of {MODEL_SIZES}")
    from faster_whisper import WhisperModel
    threads = cpu_threads or max(1, min(4, os.cpu_count() or 1))
    return WhisperModel(size, device="cpu", compute_type="int8", cpu_threads=threads)


def transcribe(model: Any, audio_path: str,
               progress: Optional[Callable[[int, float, float, str], None]] = None,
               beam_size: int = 1) -> Tuple[List[Cue], float]:
    """Run Japanese ASR. progress(n_segments, seg_end_sec, total_sec, text) is called per segment.

    Returns (cues, audio_duration_seconds). Silent/empty audio yields no cues.
    """
    audio: Any = audio_path
    if isinstance(audio_path, str) and audio_path.lower().endswith(".wav") and os.path.exists(audio_path):
        audio = load_wav(audio_path)
        if audio.size == 0:
            return [], 0.0
    segments, info = model.transcribe(audio, language="ja", vad_filter=True,
                                      beam_size=beam_size, condition_on_previous_text=False)
    total = float(getattr(info, "duration", 0.0) or 0.0)
    collected = []
    for seg in segments:
        collected.append(seg)
        if progress:
            progress(len(collected), float(seg.end), total, (seg.text or "").strip())
    return segments_to_cues(collected), total
