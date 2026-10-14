import os
import tempfile
import time

import pandas as pd
import streamlit as st

from vietsub.asr import (MODEL_SIZES, available_ram_mb, choose_default_model, extract_audio,
                         load_model, transcribe, wav_duration)
from vietsub.parser import decode_bytes, parse_subtitles
from vietsub.translator import (GoogleFreeTranslator, MockTranslator, MyMemoryTranslator,
                                default_translator, translate_cues)
from vietsub.writer import to_bytes, write_bilingual_srt, write_srt, write_vtt

MYMEMORY_DAILY_CHARS = 5000

st.set_page_config(page_title="VietSub JP→VI", page_icon="🎬", layout="wide")
st.title("🎬 VietSub: Japanese → Vietnamese subtitles")

ENGINES = ["Auto (Google → MyMemory fallback)", "Google (free)", "MyMemory (free)", "Mock (offline test)"]
with st.sidebar:
    st.header("Translation")
    engine = st.radio("Translator", ENGINES, index=0)
    batch_size = st.slider("Batch size (lines per request)", 1, 50, 20)
    st.caption(f"⚠️ MyMemory (used when Google is blocked) allows only about "
               f"{MYMEMORY_DAILY_CHARS:,} characters/day per IP. A 10–15 min video can use most of that.")


def make_translator():
    if engine.startswith("Auto"):
        tr = default_translator()
        tr.on_switch = lambda msg, exc: st.warning(f"Switching translator backend: {msg[:200]}")
        return tr
    if engine.startswith("Google"):
        return GoogleFreeTranslator()
    if engine.startswith("MyMemory"):
        return MyMemoryTranslator()
    return MockTranslator()


def run_translation(cues):
    chars = sum(len(c.text) for c in cues)
    if chars > MYMEMORY_DAILY_CHARS and not engine.startswith(("Mock", "Google")):
        st.warning(f"This file has {chars:,} characters of text, more than MyMemory's ~{MYMEMORY_DAILY_CHARS:,}/day "
                   "free quota. If Google is blocked, translation may stop partway.")
    bar = st.progress(0.0, text="Translating…")
    return translate_cues(cues, make_translator(), batch_size=batch_size,
                          progress=lambda d, t: bar.progress(d / t, text=f"Translating {d}/{t} lines"))


def preview(src, out):
    st.dataframe(pd.DataFrame({
        "#": [c.index for c in src], "Start": [c.start for c in src], "End": [c.end for c in src],
        "Japanese": [c.text for c in src], "Vietnamese": [c.text for c in out],
    }), use_container_width=True, hide_index=True)


@st.cache_resource(show_spinner="Loading speech model (first time downloads it)…")
def get_model(size: str):
    return load_model(size)


tab_video, tab_sub = st.tabs(["🎥 Video → subtitles", "📄 Subtitle file (.srt/.vtt)"])

with tab_video:
    avail = available_ram_mb()
    default_size = choose_default_model(avail)
    size = st.selectbox("Whisper model", MODEL_SIZES, index=MODEL_SIZES.index(default_size),
                        help="tiny is faster and uses less RAM; base is more accurate.")
    st.caption(f"Available RAM: {avail if avail is not None else 'unknown'} MB → default model: {default_size}. "
               "CPU only; a 10–15 min video can take several minutes.")
    video = st.file_uploader("Upload Japanese video", type=["mp4", "mkv", "mov", "webm"], key="video")
    if video is not None and st.button("Transcribe + translate", type="primary"):
        with tempfile.TemporaryDirectory() as tmp:
            vpath = os.path.join(tmp, "input" + os.path.splitext(video.name)[1].lower())
            with open(vpath, "wb") as f:
                f.write(video.getbuffer())
            t0 = time.time()
            try:
                with st.spinner("Extracting audio…"):
                    wav = extract_audio(vpath, os.path.join(tmp, "audio.wav"))
                dur = wav_duration(wav)
                model = get_model(size)
                bar = st.progress(0.0, text="Recognizing speech…")
                live = st.empty()

                def on_seg(n, end, total, text):
                    total = total or dur or 1.0
                    bar.progress(min(end / total, 1.0), text=f"Segment {n} at {end:.1f}s / {total:.1f}s")
                    live.caption(f"#{n}: {text}")

                ja, dur = transcribe(model, wav, progress=on_seg)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Speech recognition failed: {exc}")
                st.stop()
        asr_secs = time.time() - t0
        if not ja:
            st.warning("No speech detected in this video.")
            st.stop()
        st.success(f"Recognized {len(ja)} segments from {dur:.0f}s of audio in {asr_secs:.0f}s.")
        try:
            vi = run_translation(ja)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Translation failed: {exc}. The Japanese SRT can still be downloaded.")
            vi = None
        st.session_state["video_result"] = (os.path.splitext(video.name)[0], ja, vi)

    if "video_result" in st.session_state:
        base, ja, vi = st.session_state["video_result"]
        if vi:
            preview(ja, vi)
        c1, c2, c3 = st.columns(3)
        c1.download_button("⬇️ Japanese .srt", to_bytes(write_srt(ja)), f"{base}.ja.srt", "text/plain; charset=utf-8")
        if vi:
            c2.download_button("⬇️ Vietnamese .srt", to_bytes(write_srt(vi)), f"{base}.vi.srt",
                               "text/plain; charset=utf-8")
            c3.download_button("⬇️ Bilingual JA+VI .srt", to_bytes(write_bilingual_srt(ja, vi)),
                               f"{base}.ja-vi.srt", "text/plain; charset=utf-8")

with tab_sub:
    uploaded = st.file_uploader("Upload Japanese subtitle (.srt or .vtt)", type=["srt", "vtt"], key="sub")
    if uploaded is not None:
        fmt = os.path.splitext(uploaded.name)[1].lower().lstrip(".")
        try:
            text = decode_bytes(uploaded.getvalue())
        except UnicodeDecodeError:
            st.error("File is not valid UTF-8. Please re-save it as UTF-8.")
            st.stop()
        cues, warnings = parse_subtitles(text, fmt)
        for w in warnings:
            st.warning(w)
        st.info(f"Parsed {len(cues)} cues.")
        if cues and st.button("Translate to Vietnamese", type="primary"):
            try:
                out = run_translation(cues)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Translation failed: {exc}")
                st.stop()
            st.session_state["result"] = (uploaded.name, fmt, cues, out)

    if "result" in st.session_state:
        name, fmt, src, out = st.session_state["result"]
        preview(src, out)
        body = write_vtt(out) if fmt == "vtt" else write_srt(out)
        st.download_button("⬇️ Download Vietnamese subtitle", data=to_bytes(body),
                           file_name=f"{os.path.splitext(name)[0]}.vi.{fmt}", mime="text/plain; charset=utf-8")
