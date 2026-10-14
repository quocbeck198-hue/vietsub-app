# VietSub – Japanese → Vietnamese subtitle translator (Streamlit)

Upload a Japanese `.srt` (or `.vtt`), translate every cue to Vietnamese with free, keyless
backends: Google (deep-translator) with automatic fallback to MyMemory (api.mymemory.translated.net), preview JP vs VI, download the result.
Indices and timings are preserved; all I/O is UTF-8 (BOM stripped on read).

## Modes
1. **Video → subtitles**: upload mp4/mkv/mov/webm (up to 500 MB). The app extracts audio with ffmpeg, recognizes Japanese
   speech with faster-whisper (`tiny` or `base`, CPU int8, VAD on; the default is picked from available RAM), then translates to
   Vietnamese. Downloads: JA `.srt`, VI `.srt`, bilingual JA+VI `.srt`.
2. **Subtitle file**: upload a Japanese `.srt`/`.vtt` and translate it.

## Setup
```bash
sudo apt-get install -y ffmpeg   # system ffmpeg (packages.txt on Streamlit Cloud)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run the app
```bash
.venv/bin/streamlit run app.py --server.port 8501 --server.headless true
```
Open http://localhost:8501. Translator choices: **Auto (Google → MyMemory)** (default), Google, MyMemory, Mock (offline).

## CLI
```bash
.venv/bin/python translate_sample.py sample_data/sample_ja.srt sample_data/sample_vi.srt
```

## Tests
```bash
.venv/bin/python run_tests.py   # runs pytest, writes test_report.json
```

## Layout
- `vietsub/parser.py` – SRT/VTT parsing, BOM/CRLF handling, malformed-block tolerance
- `vietsub/translator.py` – GoogleFreeTranslator (batching, backoff on 429), MyMemoryTranslator (REST, throttled, backoff on 429/quota), FallbackTranslator, MockTranslator, DictTranslator
- `vietsub/writer.py` – SRT/VTT output
- `app.py` – Streamlit UI
- `architecture.md`, `tasks.json` – design docs

## Backends and limits
- Google's free endpoint CAPTCHA-blocks some server IPs (HTTP 429), and it does on the build box. In Auto mode,
  Google gets one retry, then the app switches to MyMemory for the rest of the file.
- MyMemory's anonymous quota is about 5,000 characters/day per IP (more if you pass `email=` to `MyMemoryTranslator`).
  It sends one request per line. Quality varies because it mixes translation memory with MT.
- `sample_data/sample_vi.srt` was produced for real on the build box by MyMemory (via Auto fallback).

## Measured performance (build box, 1 CPU core pinned, 17.7 s gTTS Japanese clip)
| model | ASR time | real-time factor | peak RSS (whole process) |
|---|---|---|---|
| tiny | 0.89 s | 0.05 | 306 MB |
| base | 1.58 s | 0.09 | 386 MB |

Linear extrapolation for 15 min of audio on one fast core: roughly 45 s (tiny) to 80 s (base) of ASR. Streamlit Cloud CPUs
are slower and shared, so plan for 2–5×, i.e. about 2–7 min. Translation is usually the slow part when Google is
blocked: MyMemory sends one request per line (~2.5 s/line here) and allows only ~5,000 chars/day.
The first run also downloads the model (~75 MB tiny, ~145 MB base).
