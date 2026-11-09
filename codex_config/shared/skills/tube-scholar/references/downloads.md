# Download commands

Replace placeholders with validated values and quote URLs and paths. Run these
with the requested single-video or playlist scope; a single video uses
`--no-playlist`. Inspect titles and captions before choosing languages:

```bash
yt-dlp --flat-playlist --print "%(playlist_index)s %(title)s" "<URL>"
yt-dlp --list-subs --skip-download --no-playlist "<URL>"
```

Use `%(title)s.%(ext)s` for one video, or
`%(playlist_index)s - %(title)s.%(ext)s` for playlists. For large lists, capture
output to a task log and summarize count/title instead of flooding the session.

## Subtitles

```bash
yt-dlp --write-sub --write-auto-sub --sub-langs "<languages>" --skip-download --ignore-errors -P "<dir>" -o "<template>" "<URL>"
python3 -I "$SKILL/scripts/vtt2txt.py" "<dir>"
```

Use actual track codes, such as `en` or `en,ar`. Human captions take precedence;
auto-captions fill gaps. Prefer original-language captions to auto-translated
tracks. The cleaner writes `.txt` beside `.vtt`, removing timestamps and rolling
duplicates. Keep `.vtt` for timestamp resolution.

## Audio

```bash
yt-dlp -x --audio-format mp3 --audio-quality 0 --ignore-errors -P "<dir>" -o "<template>" "<URL>"
```

## Video

```bash
yt-dlp -f "bv*[height<=1080]+ba/b[height<=1080]" --merge-output-format mp4 --ignore-errors -P "<dir>" -o "<template>" "<URL>"
```

Poll long-running jobs, keep a log and report item failures. `--ignore-errors`
does not prove every item succeeded; check output files and the log.

For 429 responses, stop rapid retries and use a bounded delayed retry. For bot or
login challenges, report the issue; browser cookies require authorization before
using `--cookies-from-browser`. Inspect `yt-dlp --version` before proposing an
upgrade; do not run Homebrew or another package manager automatically. Report
private, removed, restricted or captionless items individually.
