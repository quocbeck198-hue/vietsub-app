from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Cue:
    index: int
    start: str
    end: str
    text: str
    settings: str = ""

    def with_text(self, text: str) -> "Cue":
        return replace(self, text=text)
