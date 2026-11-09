# Study guide format

The contract between the authored content and what `build_guide.py` renders. Write the files exactly in this shape; the builder relies on these markers.

## Folder

```
~/Downloads/tube-scholar/<Folder>/
  <title>.<lang>.vtt        subtitles (subs mode)
  <title>.<lang>.txt        clean transcript (vtt2txt.py)
  meta/                     fetch_meta.py output, do not edit
  guide.json                page copy
  guide.ar.md  guide.en.md  the explanation, one file per language
  cards.ar.txt cards.en.txt Anki flashcards, one file per language
  guide.html                build_guide.py standalone HTML output
```

Languages supported by the builder: `ar` (RTL) and `en`. The first language in `guide.json` is the default edition.

## guide.json

```json
{
  "page_title": "دليل الـ AI Agents",
  "langs": ["ar", "en"],
  "h1":     {"ar": "دليل الـ AI Agents:", "en": "AI Agents:"},
  "h1_em":  {"ar": "من المبتدئ للمحترف", "en": "from beginner to pro"},
  "sub":    {"ar": "one sentence: what the guide covers", "en": "..."},
  "speaker_role": {"ar": "who the speaker is, from the video", "en": "..."},
  "resources": [
    {"url": "https://…", "title": "Exact link title",
     "kicker": {"ar": "BONUS · القسم 7", "en": "BONUS · SECTION 7"},
     "note": {"ar": "why it matters, one line", "en": "..."}}
  ],
  "socials": [{"label": "LinkedIn", "url": "https://…"}],
  "card_tags": {"ar": {"basics": "الأساسيات"}, "en": {"basics": "Basics"}},
  "card_levels": {"basics": "basic", "patterns": "mid", "security": "adv"},
  "footer_extra": {"ar": "<p>…</p>", "en": "<p>…</p>"},
  "chapter_map": {"API Design": "5", "Search at Scale (Elasticsearch)": "10.4"},
  "show_chapters": true
}
```

- `page_title`: a name of 2–4 words, never "X: explainer".
- `resources`: only links from the video description that teach something (docs, courses, papers, tools named in the talk). Skip affiliate, coaching, merch and newsletter links. Label a sponsor as a sponsor.
- `footer_extra`: disclaimers the description states (personal views, paid sponsorship).
- `chapter_map`: `{"<chapter title exactly as in meta/video.json>": "<heading number>"}`, e.g. `"API Design": "5"` or `"Search at Scale": "10.4"`. Description chapter times are typed by hand and often drift from the speech (sometimes by minutes); mapping each chapter to the guide heading where that topic starts gives it that heading's caption-accurate ▶️ time. Map every chapter whose description time is more than ~15 s off. `show_chapters: false` hides the list entirely.
- Every key except `page_title`, `langs`, `h1`, `sub` is optional.

## guide.<lang>.md

```markdown
# Any title (not rendered)

> header lines, not rendered

---

## Contents            <- optional; the builder drops everything up to the next ---
...
---

## ⚡ The 5-minute summary {tldr}

> **Short on time?** …

1. **Point one:** … [Section 1](#sec-1)
…

### Decision table: in this situation, use what?
| Situation | What to use | Section |

---

## 0. Course map {ov}

▶️ [[ts: exact words the speaker says when this part starts]]

> **Key takeaways:**
>
> - …

…body…

> **Common mistakes:**
>
> - "…a wrong belief…": wrong, because …

### 1.3 A subsection

▶️ [[ts: exact spoken words]]

## 8. Glossary {glossary}

| Term | Short definition |
|---|---|
| **ReAct loop** | Reason → Act → Observe, repeated until the answer |

## 9. Review questions {ref}

1. Scenario question? {basic}
    - [ ] plausible wrong option
    - [x] right option
    - [ ] plausible wrong option

    **Answer:** why, and which section to reread. [Section 3](#sec-3)

2. Open question? {adv}

    **Answer:** …
```

Markers per language (exact text, bold, then a blank `>` line before list items):

| Marker | ar | en |
|---|---|---|
| contents heading | `## الفهرس` | `## Contents` |
| takeaways box | `> **الخلاصة:**` | `> **Key takeaways:**` |
| mistakes box | `> **أخطاء شائعة:**` | `> **Common mistakes:**` |
| answer | `**الإجابة:**` | `**Answer:**` |
| explainer's note | `> **(ملاحظة الشارح):**` | `> **(Explainer's note):**` |

- **Levels** in `{…}` at the end of every `##` heading: `tldr`, `ov`, `basic`, `mid`, `adv`, `bonus`, `ref`. Sections with a level other than `ref` get a "done" button and show only their takeaways in quick mode. Consecutive sections with the same level form one group in the side menu.
- **Glossary** `{glossary}`: a two-column table (term, definition). The first use of each term in every other section gets a hover/tap definition; a trailing "(…)" in the term is ignored when matching, so write the term the way the text uses it.
- **Difficulty** `{basic}` / `{mid}` / `{adv}` at the end of a question line renders as an Easy/Medium/Hard pill. Flashcards get theirs from `card_levels` (tag → level), which also adds a level filter.
- **Numbering**: `## N. Title` for sections, `### N.M Title` for subsections. In-page links use `#sec-N` and `#tldr`.
- **Timestamps**: write `▶️ [[ts: …]]` with 4–10 consecutive words copied from the transcript, then run `resolve_ts.py`. It rewrites them into links and fails on any phrase the speaker never said.
- **Diagrams**: ```` ```mermaid ```` renders natively. ```` ```html ```` passes raw HTML through (keep it small and theme-neutral).
- **Concept visuals** (animated, theme-aware, RTL-aware). Use one wherever the video's idea has that shape; they beat a table or a plain diagram for it:

  ```` ```loop ```` a cycle of 2–6 stages; a dot travels it and each stage lights up as it passes (agent loops, feedback cycles, retry loops):
  ```
  center: ReAct
  - Reason: think
  - Act: do
  - Observe: check
  exit: Final Answer: the answer
  again: need more
  done: done
  caption: one line under the figure
  ```
  ```` ```matrix ```` a 2×2 quadrant, cells in reading order; `*` highlights a cell, `—` leaves it empty (mark empty cells the speaker never described):
  ```
  title: Complexity × Precision
  x: Low precision | High precision
  y: High complexity | Low complexity
  - *Smart starting point: example
  - Very hard: example
  - —
  - —
  ```
  ```` ```spectrum ```` 3–5 options along one axis, ends first and last; `*` marks the recommended one (monolith ↔ microservices, polling ↔ WebSocket, scripted ↔ autonomous):
  ```
  - Polling: asks every few seconds
  - Long polling: holds the request
  - *WebSocket: one persistent two-way connection
  ```
  ```` ```timeline ```` steps with a time budget, drawn to scale (`rest` takes what is left of `total`; `*` highlights a step):
  ```
  title: A 60-minute interview
  total: 60
  unit: min
  - Clarify requirements: 5–10
  - High-level design: 15
  - Trade-offs: the rest
  ```
  ```` ```calc ```` back-of-the-envelope maths as a chain of rows `a × b = result` (operators `×` `÷` `+` `−` need spaces around them); results are highlighted:
  ```
  title: Storage (the speaker's numbers)
  - 30M songs × 3 MB = 90 TB raw audio
  - 90 TB × 2–3 (replicas) = 180–270 TB
  note: one line under the rows
  ```
- Tables, nested lists and blockquotes are plain Markdown.

## cards.<lang>.txt

Anki import format, tab-separated, `question<TAB>answer<TAB>tag`, HTML allowed:

```
#separator:tab
#html:true
#tags column:3
#deck:<Video title> (<LANG>)
Question?	Answer with <b>bold</b> and <br> breaks.	basics
```

Tags group the filter chips on the page; name them in `guide.json → card_tags`.

## Quality bar

Write the guide for someone who wants the video's knowledge without watching it, fast.

1. **Faithful.** Every claim, number and example comes from the transcript. Anything you add (an example, a diagram's layout, an interpretation, a cell the speaker never filled) sits in an explainer's note or is labelled "(suggested example)". Paid segments are labelled as ads, and their figures as the sponsor's claims.
2. **Fast path first.** A TL;DR of 6–10 points, each linking to its section. When the video teaches choices or methods, add a decision table ("in this situation, use what").
3. **Takeaways on every taught section** (2–3 bullets) so quick mode is a complete skim.
4. **Common mistakes** (1–2 per teaching section) where a learner is likely to misread the idea. Only misreadings the content actually corrects.
5. **Scenario questions over recall.** At least half the review questions are "you face X, what do you do?" multiple choice. The wrong options must be plausible mistakes, and each answer names the section to reread.
6. **One thread example** when the video teaches a process or system: carry one concrete example through the sections instead of a new toy example each time. Mark it as a suggested example if the speaker didn't use it.
7. **Flashcards**: 40–60 for a 30–40 minute video, one fact per card, the tag set matching the guide's levels or topics, every tag mapped in `card_levels`.
10. **Difficulty on every question**, so a reader in a hurry can start with the easy ones; order the scenario questions from easy to hard.
11. **A glossary** of the terms the video relies on, so the tooltips can explain them where they first appear.
12. **Concept visuals are required**: at least two per guide, in both languages. Every set of numbers the speaker computes gets a `calc`, every time budget a `timeline`, every cycle a `loop`, every 2×2 trade-off a `matrix`, every range of options a `spectrum`. The builder warns when an edition has none.
13. **The preview passes before publishing**: `preview_guide.py` reports no horizontal overflow, and you have looked at its three screenshots.
8. **Terms stay in the original language** inside the Arabic edition (Context engineering, not a coined translation), explained in Arabic around them.
9. **The English edition is a translation of the same guide**, same sections, same anchors, not a summary.
