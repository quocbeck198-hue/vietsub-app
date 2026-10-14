import pytest

from vietsub.models import Cue
from vietsub.translator import (DictTranslator, GoogleFreeTranslator, MockTranslator,
                                translate_cues, with_retry)

CUES = [Cue(1, "00:00:01,000", "00:00:02,000", "こんにちは"),
        Cue(2, "00:00:03,000", "00:00:04,000", "一行目\n二行目"),
        Cue(5, "00:00:05,000", "00:00:06,000", "ありがとう")]


def test_mock_preserves_timing_and_index():
    out = translate_cues(CUES, MockTranslator())
    assert [(c.index, c.start, c.end) for c in out] == [(c.index, c.start, c.end) for c in CUES]
    assert out[1].text == "[VI] 一行目\n[VI] 二行目"


def test_batching():
    m = MockTranslator()
    translate_cues(CUES, m, batch_size=2)
    assert [len(c) for c in m.calls] == [2, 2]


def test_dict_translator_vietnamese():
    t = DictTranslator({"こんにちは": "Xin chào", "ありがとう": "Cảm ơn"})
    out = translate_cues(CUES, t)
    assert out[0].text == "Xin chào" and out[2].text == "Cảm ơn"


def test_retry_backoff_on_429():
    delays, state = [], {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] < 3:
            raise Exception("Server Error: 429 Too Many Requests")
        return ["ok"]

    assert with_retry(flaky, max_retries=5, base_delay=0.5, sleep=delays.append) == ["ok"]
    assert delays == [0.5, 1.0]


def test_retry_gives_up():
    with pytest.raises(Exception):
        with_retry(lambda: (_ for _ in ()).throw(Exception("429")), max_retries=2, sleep=lambda d: None)


class FakeBackend:
    def __init__(self, fail_batch=0):
        self.fail_batch = fail_batch

    def translate_batch(self, texts):
        if self.fail_batch:
            self.fail_batch -= 1
            raise Exception("429 Too Many Requests")
        return ["VI:" + t for t in texts]

    def translate(self, text):
        return "VI1:" + text


def test_google_translator_with_fake_backend_and_empty_lines():
    g = GoogleFreeTranslator(backend=FakeBackend(fail_batch=1), sleep=lambda d: None)
    assert g.translate_batch(["あ", "", "い"]) == ["VI:あ", "", "VI:い"]


def test_google_translator_falls_back_to_single():
    g = GoogleFreeTranslator(backend=FakeBackend(fail_batch=99), max_retries=1, sleep=lambda d: None)
    assert g.translate_batch(["あ"]) == ["VI1:あ"]
