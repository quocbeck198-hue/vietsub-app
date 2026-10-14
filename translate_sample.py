"""CLI: translate an SRT/VTT file JP->VI with the free Google translator."""
import os
import sys

from vietsub.parser import parse_subtitles, read_file
from vietsub.translator import default_translator, translate_cues
from vietsub.writer import save_file, write_srt, write_vtt

src, dst = sys.argv[1], sys.argv[2]
fmt = os.path.splitext(src)[1].lstrip(".").lower()
cues, _ = parse_subtitles(read_file(src), fmt)
tr = default_translator()
out = translate_cues(cues, tr)
print('backend used:', tr.active_name, file=sys.stderr)
save_file(dst, write_vtt(out) if fmt == "vtt" else write_srt(out))
for a, b in zip(cues, out):
    print(a.text.replace("\n", " / "), "=>", b.text.replace("\n", " / "))
