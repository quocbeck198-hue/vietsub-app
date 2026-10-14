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
