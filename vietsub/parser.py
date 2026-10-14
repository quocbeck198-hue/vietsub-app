import re
from typing import List, Tuple

from .models import Cue

SRT_TIME = r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
SRT_TIMING_RE = re.compile(rf"^\s*{SRT_TIME}\s*-->\s*{SRT_TIME}\s*(.*)$")
VTT_TIME = r"((?:\d{1,2}:)?\d{2}:\d{2}\.\d{3})"
VTT_TIMING_RE = re.compile(rf"^\s*{VTT_TIME}\s*-->\s*{VTT_TIME}\s*(.*)$")


def decode_bytes(data: bytes) -> str:
    """Decode as UTF-8, stripping a BOM if present."""
    return data.decode("utf-8-sig")


def _normalize(text: str) -> str:
    text = text.lstrip("\ufeff")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _blocks(text: str) -> List[List[str]]:
    blocks, cur = [], []
    for line in text.split("\n"):
        if line.strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(line.rstrip())
    if cur:
        blocks.append(cur)
    return blocks


def _norm_srt_time(t: str) -> str:
    t = t.replace(".", ",")
    hms, ms = t.split(",")
    h, m, s = hms.split(":")
    return f"{int(h):02d}:{m}:{s},{ms.ljust(3, '0')[:3]}"


def parse_srt(text: str) -> Tuple[List[Cue], List[str]]:
    """Parse SRT text. Returns (cues, warnings). Malformed blocks are skipped."""
    cues: List[Cue] = []
    warnings: List[str] = []
    for n, block in enumerate(_blocks(_normalize(text)), start=1):
        timing_pos = next((i for i, l in enumerate(block[:2]) if SRT_TIMING_RE.match(l)), None)
        if timing_pos is None:
            warnings.append(f"Block {n}: no valid timing line, skipped")
            continue
        m = SRT_TIMING_RE.match(block[timing_pos])
        index = len(cues) + 1
        if timing_pos == 1:
            try:
                index = int(block[0].strip())
            except ValueError:
                warnings.append(f"Block {n}: invalid index {block[0]!r}, renumbered")
        body = "\n".join(block[timing_pos + 1:])
        cues.append(Cue(index, _norm_srt_time(m.group(1)), _norm_srt_time(m.group(2)), body, m.group(3).strip()))
    return cues, warnings


def parse_vtt(text: str) -> Tuple[List[Cue], List[str]]:
    """Parse WebVTT text. Returns (cues, warnings)."""
    cues: List[Cue] = []
    warnings: List[str] = []
    blocks = _blocks(_normalize(text))
    if blocks and blocks[0][0].startswith("WEBVTT"):
        blocks = blocks[1:]
    else:
        warnings.append("Missing WEBVTT header")
    for n, block in enumerate(blocks, start=1):
        if block[0].startswith(("NOTE", "STYLE", "REGION")):
            continue
        timing_pos = next((i for i, l in enumerate(block[:2]) if VTT_TIMING_RE.match(l)), None)
        if timing_pos is None:
            warnings.append(f"Block {n}: no valid timing line, skipped")
            continue
        m = VTT_TIMING_RE.match(block[timing_pos])
        start, end = m.group(1), m.group(2)
        start = start if start.count(":") == 2 else "00:" + start
        end = end if end.count(":") == 2 else "00:" + end
        cues.append(Cue(len(cues) + 1, start.replace(".", ","), end.replace(".", ","),
                        "\n".join(block[timing_pos + 1:]), m.group(3).strip()))
    return cues, warnings


def parse_subtitles(text: str, fmt: str) -> Tuple[List[Cue], List[str]]:
    fmt = fmt.lower().lstrip(".")
    if fmt == "srt":
        return parse_srt(text)
    if fmt == "vtt":
        return parse_vtt(text)
    raise ValueError(f"Unsupported format: {fmt}")


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return f.read()
