# VietSub – Japanese → Vietnamese subtitle translator (Streamlit)

Upload a Japanese `.srt` (or `.vtt`), translate every cue to Vietnamese with free, keyless
backends: Google (deep-translator) with automatic fallback to MyMemory (api.mymemory.translated.net), preview JP vs VI, download the result.
Indices and timings are preserved; all I/O is UTF-8 (BOM stripped on read).

## Setup
```bash
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
