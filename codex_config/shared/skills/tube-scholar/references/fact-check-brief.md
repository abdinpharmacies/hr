# Fact-check brief

Use this brief after writing the guide and resolving timestamps, before building. Replace `<DIR>` and `$SKILL` with actual paths. For independent review, use an available reviewer agent that did not write the guide when delegation is permitted. Otherwise perform a separate review pass and record that it was not independent. Review only the language editions that exist.

---

You are auditing a study guide against the video transcript it was written from. Check each attribution against the transcript. Verify external additions against authoritative sources when needed.

Folder: `<DIR>`
- Transcript: the `.txt` file next to the `.vtt` (auto-captions: expect misspellings like "highle" for "high-level").
- Guide: `guide.ar.md` (the source edition) and `guide.en.md` (its translation). Contract: `$SKILL/references/guide-format.md`.
- Flashcards: `cards.ar.txt`, `cards.en.txt`.

Check every one of these in `guide.en.md` (it mirrors the Arabic line by line, so findings apply to both):
1. **Numbers**: every number, unit and calculation (tables, `calc` blocks, prose). Recompute arithmetic.
2. **Claims attributed to the speaker**: "the speaker says / recommends / chose". Find the passage. Flag anything he didn't say, said differently, or said with a caveat the guide dropped.
3. **Explainer's notes**: each one is labelled as an addition; check it is actually correct (not just labelled).
4. **Unlabelled additions**: content not in the transcript and not marked as an explainer's note or "(suggested example)".
5. **Quiz**: each MCQ's marked answer is right per the transcript, and no wrong option is arguably right.
6. **Flashcards**: sample up to 25 cards across all tags; each answer matches the guide and the transcript.
7. **Timestamps**: spot-check up to 10 ▶️ links: the heading's topic starts within ~20 s of that time (find the words in the `.vtt`).

Write `<DIR>/audit.md`: one line per finding, most serious first, each with `severity (wrong / unsupported / unclear)`, the guide location (section number), what the guide says, what the transcript says (quote ≤ 25 words with its approximate time), and the fix. End with counts per category and "checked N numbers, N claims, N notes, N questions, N cards".
Do not edit the guide files. Report back only the counts and the top five findings.
