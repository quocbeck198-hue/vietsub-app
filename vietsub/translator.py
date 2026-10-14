import time
from typing import Callable, Dict, List, Optional, Protocol, Sequence

from .models import Cue


class Translator(Protocol):
    def translate_batch(self, texts: Sequence[str]) -> List[str]:
        ...


class RateLimitError(Exception):
    """Raised when the remote service answers HTTP 429."""


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return isinstance(exc, RateLimitError) or "429" in msg or "too many requests" in msg


def with_retry(func: Callable[[], List[str]], max_retries: int = 5, base_delay: float = 1.0,
               sleep: Callable[[float], None] = time.sleep) -> List[str]:
    """Call func, retrying with exponential backoff on 429 / transient errors."""
    attempt = 0
    while True:
        try:
            return func()
        except Exception as exc:  # noqa: BLE001 - remote libs raise many types
            attempt += 1
            if attempt > max_retries:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            if not _is_rate_limit(exc):
                delay = base_delay
            sleep(delay)


class MockTranslator:
    """Offline translator: prefixes text, records calls."""

    def __init__(self, prefix: str = "[VI] "):
        self.prefix = prefix
        self.calls: List[List[str]] = []

    def translate_batch(self, texts: Sequence[str]) -> List[str]:
        self.calls.append(list(texts))
        return [self.prefix + t if t.strip() else t for t in texts]


class DictTranslator:
    """Offline translator backed by a lookup table (falls back to original)."""

    def __init__(self, table: Dict[str, str]):
        self.table = table

    def translate_batch(self, texts: Sequence[str]) -> List[str]:
        return [self.table.get(t, t) for t in texts]


class GoogleFreeTranslator:
    """Free Google Translate via deep-translator (no API key)."""

    def __init__(self, source: str = "ja", target: str = "vi", max_retries: int = 5,
                 base_delay: float = 1.0, sleep: Callable[[float], None] = time.sleep,
                 backend: Optional[object] = None):
        if backend is None:
            from deep_translator import GoogleTranslator
            backend = GoogleTranslator(source=source, target=target)
        self.backend = backend
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.sleep = sleep

    def _one(self, text: str) -> str:
        if not text.strip():
            return text
        return with_retry(lambda: [self.backend.translate(text) or text],
                          self.max_retries, self.base_delay, self.sleep)[0]

    def translate_batch(self, texts: Sequence[str]) -> List[str]:
        texts = list(texts)
        non_empty = [t for t in texts if t.strip()]
        if not non_empty:
            return texts
        try:
            out = with_retry(lambda: list(self.backend.translate_batch(non_empty)),
                             self.max_retries, self.base_delay, self.sleep)
            if len(out) != len(non_empty):
                raise ValueError("batch size mismatch")
        except Exception:  # noqa: BLE001 - fall back to per-item translation
            out = [self._one(t) for t in non_empty]
        it = iter(out)
        return [(next(it) or t) if t.strip() else t for t in texts]


def translate_cues(cues: Sequence[Cue], translator: Translator, batch_size: int = 20,
                   progress: Optional[Callable[[int, int], None]] = None) -> List[Cue]:
    """Translate cues line-by-line (keeps multi-line layout), preserving index/timing."""
    lines: List[str] = []
    owners: List[int] = []
    for i, c in enumerate(cues):
        for line in c.text.split("\n"):
            lines.append(line)
            owners.append(i)
    translated: List[str] = []
    for start in range(0, len(lines), batch_size):
        chunk = lines[start:start + batch_size]
        res = translator.translate_batch(chunk)
        if len(res) != len(chunk):
            raise ValueError("Translator returned wrong number of items")
        translated.extend(res)
        if progress:
            progress(min(start + batch_size, len(lines)), len(lines))
    per_cue: List[List[str]] = [[] for _ in cues]
    for owner, text in zip(owners, translated):
        per_cue[owner].append(text)
    return [c.with_text("\n".join(per_cue[i])) for i, c in enumerate(cues)]


class MyMemoryTranslator:
    """Free MyMemory REST API (api.mymemory.translated.net), no key required.

    Sends one request per line (MyMemory has no batch endpoint), throttled by
    `min_interval` seconds, with exponential backoff on HTTP 429 / quota errors.
    """

    URL = "https://api.mymemory.translated.net/get"

    def __init__(self, source: str = "ja-JP", target: str = "vi-VN", email: Optional[str] = None,
                 max_retries: int = 5, base_delay: float = 2.0, min_interval: float = 0.3,
                 sleep: Callable[[float], None] = time.sleep,
                 fetch: Optional[Callable[[str], dict]] = None, timeout: float = 20.0):
        self.langpair = f"{source}|{target}"
        self.email = email
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.min_interval = min_interval
        self.sleep = sleep
        self.timeout = timeout
        self.fetch = fetch or self._http_fetch

    def _http_fetch(self, url: str) -> dict:
        import json
        import urllib.error
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "vietsub-app/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise RateLimitError("HTTP 429 from MyMemory") from exc
            raise

    def _url(self, text: str) -> str:
        from urllib.parse import urlencode
        params = {"q": text, "langpair": self.langpair}
        if self.email:
            params["de"] = self.email
        return f"{self.URL}?{urlencode(params)}"

    def _one(self, text: str) -> str:
        if not text.strip():
            return text

        def call() -> List[str]:
            data = self.fetch(self._url(text))
            status = int(data.get("responseStatus") or 0)
            if status == 429 or data.get("quotaFinished"):
                raise RateLimitError(f"MyMemory 429/quota: {data.get('responseDetails')}")
            if status != 200:
                raise RuntimeError(f"MyMemory error {status}: {data.get('responseDetails')}")
            out = (data.get("responseData") or {}).get("translatedText") or ""
            if "MYMEMORY WARNING" in out.upper():
                raise RateLimitError(out)
            return [out.strip() or text]

        result = with_retry(call, self.max_retries, self.base_delay, self.sleep)[0]
        if self.min_interval:
            self.sleep(self.min_interval)
        return result

    def translate_batch(self, texts: Sequence[str]) -> List[str]:
        return [self._one(t) for t in texts]


class FallbackTranslator:
    """Try each translator in order; once one fails, stick with the next one."""

    def __init__(self, factories: Sequence[Callable[[], Translator]],
                 on_switch: Optional[Callable[[str, Exception], None]] = None):
        if not factories:
            raise ValueError("need at least one translator")
        self.factories = list(factories)
        self.on_switch = on_switch
        self._pos = 0
        self._current: Optional[Translator] = None
        self.errors: List[str] = []

    @property
    def active_name(self) -> str:
        return type(self._current).__name__ if self._current else "none"

    def translate_batch(self, texts: Sequence[str]) -> List[str]:
        while self._pos < len(self.factories):
            try:
                if self._current is None:
                    self._current = self.factories[self._pos]()
                return self._current.translate_batch(texts)
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"{self.factories[self._pos]}: {exc}")
                self._pos += 1
                self._current = None
                if self.on_switch:
                    self.on_switch(str(exc), exc)
        raise RuntimeError("All translators failed: " + " | ".join(self.errors))


def default_translator(fast_fail: bool = True) -> FallbackTranslator:
    """Google first (few retries so a block is detected fast), then MyMemory."""
    g_retries = 1 if fast_fail else 5
    return FallbackTranslator([
        lambda: GoogleFreeTranslator(max_retries=g_retries, base_delay=1.0),
        lambda: MyMemoryTranslator(),
    ])
