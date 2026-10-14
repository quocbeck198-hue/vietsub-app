from vietsub.parser import decode_bytes, parse_srt, parse_vtt, read_file
from vietsub.writer import save_file, to_bytes, write_srt, write_vtt

JP = "1\n00:00:01,000 --> 00:00:03,500\nこんにちは、世界！\n\n2\n00:00:04,000 --> 00:00:06,000\n漢字とひらがなとカタカナ\n二行目です\n"


def test_parse_japanese():
    cues, w = parse_srt(JP)
    assert w == []
    assert len(cues) == 2
    assert cues[0].text == "こんにちは、世界！"
    assert cues[1].start == "00:00:04,000"


def test_multiline_cue():
    cues, _ = parse_srt(JP)
    assert cues[1].text == "漢字とひらがなとカタカナ\n二行目です"


def test_roundtrip_japanese():
    cues, _ = parse_srt(JP)
    again, _ = parse_srt(write_srt(cues))
    assert again == cues


def test_roundtrip_vietnamese_diacritics(tmp_path):
    vi = "1\n00:00:01,000 --> 00:00:02,000\nTiếng Việt có dấu: ắ ằ ẳ ẵ ặ ơ ư đ Ở Ữ\n"
    cues, _ = parse_srt(vi)
    p = tmp_path / "vi.srt"
    save_file(str(p), write_srt(cues))
    assert parse_srt(read_file(str(p)))[0] == cues
    assert "ặ" in p.read_bytes().decode("utf-8")


def test_empty_srt():
    assert parse_srt("") == ([], [])
    assert parse_srt("\n\n  \n") == ([], [])
    assert write_srt([]) == ""


def test_malformed_blocks():
    text = "1\nnot a timing\nfoo\n\nabc\n00:00:01,000 --> 00:00:02,000\nバー\n\n3\n00:00:03,000 --> 00:00:04,000\n正常\n"
    cues, w = parse_srt(text)
    assert [c.text for c in cues] == ["バー", "正常"]
    assert len(w) == 2


def test_bom_bytes_and_file(tmp_path):
    raw = "\ufeff".encode("utf-8") + JP.encode("utf-8")
    text = decode_bytes(raw)
    assert not text.startswith("\ufeff")
    assert parse_srt(text)[0][0].index == 1
    p = tmp_path / "bom.srt"
    p.write_bytes(raw)
    assert parse_srt(read_file(str(p)))[0][0].text == "こんにちは、世界！"


def test_crlf():
    cues, _ = parse_srt(JP.replace("\n", "\r\n"))
    assert cues[1].text == "漢字とひらがなとカタカナ\n二行目です"


def test_long_unicode_line():
    long = "日本語のテキスト🎌" * 500 + "Tiếng Việt" * 200
    text = f"1\n00:00:01,000 --> 00:00:02,000\n{long}\n"
    cues, _ = parse_srt(text)
    assert cues[0].text == long
    assert parse_srt(write_srt(cues))[0][0].text == long
    assert to_bytes(write_srt(cues)).decode("utf-8") == write_srt(cues)


def test_vtt_parse_and_write():
    vtt = "WEBVTT\n\nNOTE comment\n\n00:01.000 --> 00:02.500 align:start\nおはよう\n\ncue2\n00:00:03.000 --> 00:00:04.000\nさようなら\n"
    cues, w = parse_vtt(vtt)
    assert w == []
    assert [c.text for c in cues] == ["おはよう", "さようなら"]
    assert cues[0].start == "00:00:01,000"
    assert cues[0].settings == "align:start"
    out = write_vtt(cues)
    assert out.startswith("WEBVTT")
    assert parse_vtt(out)[0] == cues
