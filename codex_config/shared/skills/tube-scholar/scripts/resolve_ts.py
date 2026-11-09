#!/usr/bin/env python3
"""Turn `▶️ [[ts: exact words from the transcript]]` markers into timestamped video links.

Usage: resolve_ts.py <guide-dir>

Reads the .vtt in <guide-dir> and meta/video.json, rewrites every guide.*.md in
place, and exits 1 listing any phrase it could not find (fix the wording and rerun).
Anchoring each link to words the speaker actually said is the accuracy check:
a section with no matching phrase is a section the video does not cover.
"""
import json, re, sys
from pathlib import Path


def words_with_times(vtt):
    """(seconds, word) for every spoken word; word-level timings when present, cue start otherwise."""
    words, cur, seen_tags = [], 0, '<c>' in vtt
    for line in vtt.splitlines():
        m = re.match(r'(\d\d):(\d\d):(\d\d)\.\d+ -->', line) or re.match(r'(\d\d):(\d\d)\.\d+ -->', line)
        if m:
            g = [int(x) for x in m.groups()]
            cur = g[0] * 3600 + g[1] * 60 + g[2] if len(g) == 3 else g[0] * 60 + g[1]
            continue
        if seen_tags:
            if '<c>' not in line:
                continue  # auto-subs repeat each line once without tags; skip the copy
            first = line.split('<')[0].strip()
            if first:
                words.append((cur, first))
            for t, w in re.findall(r'<(\d\d:\d\d:\d\d)\.\d+><c>\s*([^<]*)</c>', line):
                h, mi, s = map(int, t.split(':'))
                words.append((h * 3600 + mi * 60 + s, w.strip()))
        elif line.strip() and not line.startswith(('WEBVTT', 'Kind:', 'Language:', 'NOTE')) and not line.strip().isdigit():
            words += [(cur, w) for w in re.sub(r'<[^>]+>', '', line).split()]
    return words


def norm(w):
    return re.sub(r'[^\w]', '', w.lower())


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    gdir = Path(sys.argv[1]).expanduser()
    vtts = sorted(gdir.glob('*.vtt'))
    if not vtts:
        sys.exit('no .vtt in the guide folder: download subtitles first')
    vid = json.loads((gdir / 'meta/video.json').read_text())['id']
    stream = words_with_times(vtts[0].read_text())
    seq = [norm(w) for _, w in stream]
    missing = []

    def find(phrase):
        p = [norm(x) for x in phrase.split() if norm(x)]
        for i in range(len(seq) - len(p) + 1):
            if seq[i:i + len(p)] == p:
                return stream[i][0]
        return None

    def sub(m):
        t = find(m[1])
        if t is None:
            missing.append(m[1]); return m[0]
        return f'▶️ [{t // 60:02d}:{t % 60:02d}](https://www.youtube.com/watch?v={vid}&t={t}s)'

    for md in sorted(gdir.glob('guide.*.md')):
        text = md.read_text()
        new = re.sub(r'▶️ \[\[ts:\s*(.*?)\]\]', sub, text)
        if new != text:
            md.write_text(new)
    if missing:
        print('not found in transcript (reword to the exact spoken words):')
        print('\n'.join(f'  - {p}' for p in dict.fromkeys(missing)))
        sys.exit(1)
    print('all timestamps resolved')


if __name__ == '__main__':
    main()
