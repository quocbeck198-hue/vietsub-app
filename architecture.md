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

## v3: Video → subtitles (speech recognition)
| Module | Responsibility |
|---|---|
| `vietsub/asr.py` | `extract_audio` (ffmpeg → 16 kHz mono WAV; PyAV fallback), `load_wav` (numpy, no PyAV needed), `load_model` (faster-whisper tiny/base, CPU int8), `transcribe` (language=ja, vad_filter, per-segment progress callback), `segments_to_cues`, `format_srt_time`, RAM-based `choose_default_model` |
| `vietsub/writer.py` | adds `write_bilingual_srt` (JA line(s) then VI line(s), same timing) |
| `app.py` | Two tabs: **Video → subtitles** (upload mp4/mkv/mov/webm → extract → ASR with progress → translate → download JA/VI/bilingual SRT) and **Subtitle file** (the original .srt/.vtt mode). Model cached with `st.cache_resource`. The sidebar warns about MyMemory's ~5,000 chars/day limit. |

Flow: upload → temp file → ffmpeg WAV → numpy float32 → WhisperModel.transcribe → Cue list → translate_cues(Auto Google→MyMemory) → SRT bytes.

Deployment: `packages.txt` (ffmpeg apt package), `.streamlit/config.toml` (`maxUploadSize = 500` MB).
