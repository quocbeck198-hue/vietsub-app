import os

import pandas as pd
import streamlit as st

from vietsub.parser import decode_bytes, parse_subtitles
from vietsub.translator import (GoogleFreeTranslator, MockTranslator, MyMemoryTranslator,
                                default_translator, translate_cues)
from vietsub.writer import to_bytes, write_srt, write_vtt

st.set_page_config(page_title="VietSub JP→VI", page_icon="🎬", layout="wide")
st.title("🎬 VietSub: Japanese → Vietnamese subtitles")

uploaded = st.file_uploader("Upload Japanese subtitle (.srt or .vtt)", type=["srt", "vtt"])
ENGINES = ["Auto (Google → MyMemory fallback)", "Google (free)", "MyMemory (free)", "Mock (offline test)"]
engine = st.radio("Translator", ENGINES, index=0, horizontal=True)
batch_size = st.slider("Batch size (lines per request)", 1, 50, 20)

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
        if engine.startswith("Auto"):
            translator = default_translator()
            translator.on_switch = lambda msg, exc: st.warning(f"Switching translator backend: {msg[:200]}")
        elif engine.startswith("Google"):
            translator = GoogleFreeTranslator()
        elif engine.startswith("MyMemory"):
            translator = MyMemoryTranslator()
        else:
            translator = MockTranslator()
        bar = st.progress(0.0, text="Translating…")
        try:
            out = translate_cues(cues, translator, batch_size=batch_size,
                                 progress=lambda d, t: bar.progress(d / t, text=f"{d}/{t} lines"))
        except Exception as exc:  # noqa: BLE001
            st.error(f"Translation failed: {exc}")
            st.stop()
        st.session_state["result"] = (uploaded.name, fmt, cues, out)

if "result" in st.session_state:
    name, fmt, src, out = st.session_state["result"]
    df = pd.DataFrame({
        "#": [c.index for c in src],
        "Start": [c.start for c in src],
        "End": [c.end for c in src],
        "Japanese": [c.text for c in src],
        "Vietnamese": [c.text for c in out],
    })
    st.dataframe(df, use_container_width=True, hide_index=True)
    body = write_vtt(out) if fmt == "vtt" else write_srt(out)
    base = os.path.splitext(name)[0]
    st.download_button("⬇️ Download Vietnamese subtitle", data=to_bytes(body),
                       file_name=f"{base}.vi.{fmt}", mime="text/plain; charset=utf-8")
