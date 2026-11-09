# Study workflow

`$SKILL` is the skill directory; `<dir>` is a video's output directory. Use the
Python interpreter with `markdown` available for builders. Read `guide-format.md`
for the JSON/Markdown contract before authoring content.

1. Retrieve captions and clean them using `downloads.md`. Read the full transcript.
2. Fetch metadata and images:
   ```bash
   python3 -I "$SKILL/scripts/fetch_meta.py" "<URL>" "<dir>" --related ID1,ID2,ID3
   ```
   Omit `--related` when no suitable related videos are known. Prefer videos
   recommended in the description; otherwise inspect relevant videos from the
   speaker. The helper optionally uses macOS `sips`; it is not required on Linux.
3. Use `meta/video.json` and description chapters to plan the actual taught topics.
   Write `guide.ar.md`, `guide.en.md`, `cards.ar.txt`, `cards.en.txt` and `guide.json`
   for the requested languages. Align bilingual sections, numbers and anchors.
   Add `tags` if absent and map every description chapter to its first heading.
   Place `▶️ [[ts: exact spoken words]]` under section/subsection headings.
4. Resolve timestamps:
   ```bash
   python3 -I "$SKILL/scripts/resolve_ts.py" "<dir>"
   ```
   Fix unmatched phrases from the actual transcript and rerun. Do not invent times.
5. Use `fact-check-brief.md` for an independent review with an available reviewer
   agent when delegation is permitted. Pass the guide, transcript and brief;
   select a reviewer supported by the current host. If unavailable, do a separate
   review pass and disclose that it was not independent. Fix `wrong` and
   `unsupported` findings in every edition and cards; label unresolved claims.
6. Build standalone HTML for Codex/OpenCode:
   ```bash
   python3 "$SKILL/scripts/build_guide.py" "<dir>" --standalone
   ```
   The builder rejects unresolved placeholders and invalid chapter timestamps.
   Check duplicate IDs, fragment targets and extracted JavaScript with
   `node --check`. Images are embedded, but fonts and Mermaid use external CDNs;
   do not describe the page as fully offline.
7. Preview using an available browser or:
   ```bash
   python3 -I "$SKILL/scripts/preview_guide.py" "<dir>/guide.html"
   ```
   Inspect desktop/phone screenshots and every concept visual, and check
   horizontal overflow. Fix source content, rebuild and recheck actual failures.
   When browser/CDN access is missing, report unverified visuals; a skipped Mermaid
   check is not a pass. The helper is aimed at guides; inspect hubs separately.
8. Export a cheat sheet when requested or as part of the full guide package:
   ```bash
   python3 -I "$SKILL/scripts/cheatsheet.py" "<dir>"
   ```
   Verify PDFs exist and inspect rendered pages. Missing browser support leaves
   the HTML deliverable usable; report that the PDF export is incomplete.
9. Deliver the files. Publish only to an explicitly authorized destination using
   available tools, then save its real URL as `artifact_url` in `guide.json`.

## Playlist hub

Build each requested guide in order. For a local hub, set each `artifact_url` to
its HTML path relative to the hub, such as `lesson-01/guide.html`; this field also
accepts a real published URL when publishing was authorized. Then run:

```bash
python3 "$SKILL/scripts/build_hub.py" "<playlist-dir>/hub.html" "<playlist title>" "<video-dir-1>" "<video-dir-2>"
```

Check that every link opens the right guide and preview desktop/phone layouts.
Rebuild after changing `.md`, `.txt` or `guide.json`; never hand-edit generated
`guide.html`. Rerun timestamp resolution and review affected claims after edits.
