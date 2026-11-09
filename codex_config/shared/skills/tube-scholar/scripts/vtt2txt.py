#!/usr/bin/env python3
"""Convert YouTube .vtt subtitles into clean readable .txt files.

Usage: vtt2txt.py <file.vtt | directory> [...]
Strips the WEBVTT header, cue timings, inline tags and the rolling duplicate
lines that auto-generated captions repeat, then wraps text into paragraphs.
"""
import re
import sys
import textwrap
from pathlib import Path

TIMING = re.compile(r"^\d{2}:\d{2}(:\d{2})?\.\d{3} --> ")
TAG = re.compile(r"<[^>]+>")
HEADER = ("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")


def clean(vtt: str) -> str:
    lines, last = [], None
    for raw in vtt.splitlines():
        line = TAG.sub("", raw).replace("&nbsp;", " ").strip()
        if not line or line.startswith(HEADER) or TIMING.match(line) or line.isdigit():
            continue
        if line == last:
            continue
        lines.append(line)
        last = line
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    paragraphs, chunk = [], []
    for s in sentences:
        chunk.append(s)
        if len(" ".join(chunk)) > 600:
            paragraphs.append(" ".join(chunk))
            chunk = []
    if chunk:
        paragraphs.append(" ".join(chunk))
    return "\n\n".join(textwrap.fill(p, 100) for p in paragraphs) + "\n"


def main(args):
    if not args:
        sys.exit(__doc__)
    files = []
    for arg in args:
        p = Path(arg).expanduser()
        files += sorted(p.glob("*.vtt")) if p.is_dir() else [p]
    for f in files:
        out = f.with_suffix(".txt")
        out.write_text(clean(f.read_text(encoding="utf-8")), encoding="utf-8")
        print(out)


if __name__ == "__main__":
    main(sys.argv[1:])
