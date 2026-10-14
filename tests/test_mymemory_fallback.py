import pytest

from vietsub.models import Cue
from vietsub.translator import (FallbackTranslator, MockTranslator, MyMemoryTranslator,
                                RateLimitError, translate_cues)


def ok(text):
    return {"responseStatus": 200, "quotaFinished": False,
            "responseData": {"translatedText": text}}


def test_mymemory_parses_response_and_url():
    urls = []

    def fetch(url):
        urls.append(url)
        return ok("Xin chào thế giới")

    t = MyMemoryTranslator(fetch=fetch, sleep=lambda d: None)
    assert t.translate_batch(["こんにちは", ""]) == ["Xin chào thế giới", ""]
    assert len(urls) == 1
    assert "langpair=ja-JP%7Cvi-VN" in urls[0]


def test_mymemory_retries_on_429_status():
    seq = [{"responseStatus": 429, "responseDetails": "slow down"}, ok("Cảm ơn")]
    delays = []
    t = MyMemoryTranslator(fetch=lambda u: seq.pop(0), sleep=delays.append,
                           base_delay=2.0, min_interval=0)
    assert t.translate_batch(["ありがとう"]) == ["Cảm ơn"]
    assert delays == [2.0]


def test_mymemory_raises_after_quota_exhausted():
    t = MyMemoryTranslator(fetch=lambda u: {"responseStatus": 200, "quotaFinished": True},
                           sleep=lambda d: None, max_retries=2)
    with pytest.raises(RateLimitError):
        t.translate_batch(["あ"])


class Broken:
    def translate_batch(self, texts):
        raise RuntimeError("429 blocked")


def test_fallback_switches_and_sticks():
    switched = []
    mock = MockTranslator(prefix="MM:")
    f = FallbackTranslator([Broken, lambda: mock], on_switch=lambda m, e: switched.append(m))
    cues = [Cue(1, "00:00:01,000", "00:00:02,000", "猫"), Cue(2, "00:00:03,000", "00:00:04,000", "犬")]
    out = translate_cues(cues, f, batch_size=1)
    assert [c.text for c in out] == ["MM:猫", "MM:犬"]
    assert len(switched) == 1
    assert f.active_name == "MockTranslator"


def test_fallback_all_fail():
    with pytest.raises(RuntimeError, match="All translators failed"):
        FallbackTranslator([Broken, Broken]).translate_batch(["x"])
