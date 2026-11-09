#!/usr/bin/env python3
"""Fetch a video's metadata and images for the study guide.

Usage: fetch_meta.py <URL> <guide-dir> [--related ID,ID,...] [--related-search "QUERY"]

Writes <guide-dir>/meta/: video.json (the fields the guide uses), thumb.jpg,
avatar.jpg, banner.jpg, and for each related video rel_<id>.jpg plus related.json.
Related videos: the --related ids, or else the top 3 YouTube results for --related-search
(use it when the description recommends no videos, e.g. "<speaker name> <topic>").
Images are shrunk with macOS `sips` when present, so the page stays small.
"""
import json, shutil, subprocess, sys, urllib.request
from pathlib import Path

KEEP = ('id', 'title', 'channel', 'channel_id', 'channel_url', 'uploader_id', 'channel_follower_count', 'channel_is_verified',
        'upload_date', 'duration_string', 'view_count', 'like_count', 'comment_count', 'categories', 'tags', 'chapters',
        'description', 'language', 'thumbnail')


def ytdlp_json(*args):
    out = subprocess.run(['yt-dlp', '-J', *args], capture_output=True, text=True)
    if out.returncode:
        sys.exit(f'yt-dlp failed: {out.stderr.strip().splitlines()[-1] if out.stderr.strip() else out.returncode}')
    return json.loads(out.stdout)


def download(url, dest):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            dest.write_bytes(r.read())
        return True
    except OSError as e:
        print(f'skip {dest.name}: {e}')
        return False


def shrink(path, *sips_args):
    if shutil.which('sips') and path.exists():
        subprocess.run(['sips', '-s', 'format', 'jpeg', *sips_args, str(path), '--out', str(path)], capture_output=True)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    url, gdir = sys.argv[1], Path(sys.argv[2]).expanduser()
    related = sys.argv[sys.argv.index('--related') + 1].split(',') if '--related' in sys.argv else []
    search = sys.argv[sys.argv.index('--related-search') + 1] if '--related-search' in sys.argv else ''
    meta = gdir / 'meta'
    meta.mkdir(parents=True, exist_ok=True)

    v = ytdlp_json('--skip-download', '--no-playlist', url)
    (meta / 'video.json').write_text(json.dumps({k: v.get(k) for k in KEEP}, ensure_ascii=False, indent=1))
    if download(f'https://i.ytimg.com/vi/{v["id"]}/maxresdefault.jpg', meta / 'thumb.jpg') or download(v.get('thumbnail', ''), meta / 'thumb.jpg'):
        shrink(meta / 'thumb.jpg', '-s', 'formatOptions', '72', '-Z', '1100')

    if v.get('channel_url'):
        ch = ytdlp_json('--flat-playlist', '--playlist-items', '0', v['channel_url'])
        thumbs = {t.get('id'): t['url'] for t in ch.get('thumbnails', []) if t.get('id')}
        if 'avatar_uncropped' in thumbs and download(thumbs['avatar_uncropped'].replace('=s0', '=s240'), meta / 'avatar.jpg'):
            shrink(meta / 'avatar.jpg', '-s', 'formatOptions', '80', '-Z', '160')
        if 'banner_uncropped' in thumbs and download(thumbs['banner_uncropped'].replace('=s0', '=w1600'), meta / 'banner.jpg'):
            shrink(meta / 'banner.jpg', '-s', 'formatOptions', '70', '-Z', '1400')
            if shutil.which('sips'):  # keep the centre strip, where channel art puts its text
                subprocess.run(['sips', '-c', '300', '1400', str(meta / 'banner.jpg'), '--out', str(meta / 'banner.jpg')], capture_output=True)

    if not related and search:
        out = subprocess.run(['yt-dlp', '--flat-playlist', '--print', '%(id)s\t%(title)s', f'ytsearch10:{search}'], capture_output=True, text=True)
        seen = {v['title'].lower()}
        for line in out.stdout.splitlines():
            i, _, t = line.partition('\t')
            if i != v['id'] and t.lower() not in seen and len(related) < 3:
                related.append(i); seen.add(t.lower())
    rel = []
    for rid in filter(None, related):
        out = subprocess.run(['yt-dlp', '--print', '%(id)s\t%(title)s\t%(duration_string)s\t%(view_count)s', f'https://www.youtube.com/watch?v={rid}'],
                             capture_output=True, text=True)
        if out.returncode or not out.stdout.strip():
            print(f'skip related {rid}: unavailable'); continue
        i, title, dur, views = out.stdout.strip().split('\t')
        download(f'https://i.ytimg.com/vi/{i}/mqdefault.jpg', meta / f'rel_{i}.jpg')
        rel.append({'id': i, 'title': title, 'duration': dur, 'views': int(views) if views.isdigit() else None})
    (meta / 'related.json').write_text(json.dumps(rel, ensure_ascii=False, indent=1))
    print(f'meta ready: {v["title"]} · {len(v.get("chapters") or [])} chapters · {len(rel)} related')


if __name__ == '__main__':
    main()
