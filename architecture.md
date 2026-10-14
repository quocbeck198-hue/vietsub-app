# VietSub – Architecture

Streamlit app translating Japanese subtitles (.srt / .vtt) to Vietnamese.

## Modules
| Module | Responsibility |
|---|---|
| `vietsub/models.py` | `Cue` dataclass (index, start, end, text, settings) |
| `vietsub/parser.py` | Decode bytes (utf-8-sig, strips BOM), parse SRT and WebVTT into `Cue` lists; skip malformed blocks, collect warnings |
| `vietsub/translator.py` | `Translator` protocol; `GoogleFreeTranslator` (deep-translator, no key) with batching, retry + exponential backoff on HTTP 429 / transient errors; `MockTranslator` / `DictTranslator` offline; `translate_cues()` preserving timing/indices |
| `vietsub/writer.py` | Serialize cues to SRT / VTT text and UTF-8 bytes |
| `app.py` | Streamlit UI: upload, translate with progress, preview table JP vs VI, download |

## Data flow
upload bytes -> `decode_bytes` -> `parse_subtitles` -> `translate_cues(translator)` -> `write_srt/write_vtt` -> `to_bytes` (UTF-8, no BOM) -> download.

## Encoding policy
All file reads: `encoding="utf-8-sig"`; all writes: `encoding="utf-8"`. Uploaded bytes decoded with `utf-8-sig`.

## Multi-line cues
Lines in a cue are joined with `\n`; for batching, each cue is sent as one item and line breaks preserved by translating line by line within a cue.
