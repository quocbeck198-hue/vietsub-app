from typing import Iterable

from .models import Cue


def write_srt(cues: Iterable[Cue]) -> str:
    parts = []
    for c in cues:
        timing = f"{c.start} --> {c.end}" + (f" {c.settings}" if c.settings else "")
        parts.append(f"{c.index}\n{timing}\n{c.text}\n")
    return "\n".join(parts)


def write_vtt(cues: Iterable[Cue]) -> str:
    parts = ["WEBVTT\n"]
    for c in cues:
        timing = f"{c.start.replace(',', '.')} --> {c.end.replace(',', '.')}" + (f" {c.settings}" if c.settings else "")
        parts.append(f"{c.index}\n{timing}\n{c.text}\n")
    return "\n".join(parts)


def to_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def save_file(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_bilingual_srt(src: Iterable[Cue], dst: Iterable[Cue]) -> str:
    """SRT where each cue shows the source text then the translation, same timing."""
    src, dst = list(src), list(dst)
    if len(src) != len(dst):
        raise ValueError("source and translated cue counts differ")
    merged = [s.with_text(f"{s.text}\n{d.text}") for s, d in zip(src, dst)]
    return write_srt(merged)
