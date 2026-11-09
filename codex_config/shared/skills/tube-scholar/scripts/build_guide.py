#!/usr/bin/env python3
"""Build a bilingual study-guide page (one self-contained HTML file) for a YouTube video.

Usage: build_guide.py <guide-dir> [--out <file.html>] [--standalone]

--standalone adds the document skeleton and the Mermaid library, for hosting the page
in a browser or on a static host. Mermaid and web fonts require CDN access.

<guide-dir> holds (see references/guide-format.md):
  guide.json              page copy: langs, titles, resources, socials
  guide.<lang>.md         the explanation, one per language (ar, en)
  cards.<lang>.txt        Anki-format flashcards, one per language
  meta/                   written by fetch_meta.py (video.json, images, related.json)
Needs the `markdown` package: run it with the venv python from SKILL.md.
"""
import base64, html, json, math, re, sys
from datetime import date
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit('markdown package missing: run with ~/.cache/tube-scholar/venv/bin/python (see SKILL.md, study mode)')

ASSETS = Path(__file__).resolve().parent.parent / 'assets'
RTL = {'ar'}
LEVELS = ['ov', 'basic', 'mid', 'adv', 'bonus', 'ref']
LV_EN = {'ov': 'OVERVIEW', 'basic': 'BASICS', 'mid': 'INTERMEDIATE', 'adv': 'ADVANCED', 'bonus': 'BONUS', 'ref': 'REFERENCE'}
AR_MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
EN_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

UI = {
 'ar': dict(
    marks=dict(contents='الفهرس', kt='الخلاصة:', mx='أخطاء شائعة:', ans='الإجابة:', note='(ملاحظة الشارح)'),
    diff=dict(basic='سهل', mid='متوسط', adv='متقدم'), kt='الخلاصة', mx='أخطاء شائعة', ans_sum='اعرض الإجابة', quiz='نتيجتك في أسئلة السيناريو:', retry='أعد المحاولة',
    rt=lambda m: {1: 'دقيقة قراءة', 2: 'دقيقتين قراءة'}.get(m, f'{m} دقايق قراءة' if m <= 10 else f'{m} دقيقة قراءة'), wpm=170,
    done='خلصت القسم ده', done_on='خلصته', quick='الوضع السريع', tldr_lvl='<bdi>TL;DR</bdi> · للمستعجل', tldr_sm='النقط الأساسية في الفيديو كله، في دقايق',
    groups=dict(start='ابدأ هنا', ov='نظرة عامة', basic='الأساسيات', mid='المتوسط', adv='المتقدم', bonus='إضافي', ref='مرجع ومراجعة'),
    lv=dict(ov='نظرة عامة', basic='الأساسيات', mid='المتوسط', adv='المتقدم', bonus='إضافي', ref='مرجع'),
    nav_ch='فصول الفيديو الرسمية', nav_res='المصادر والروابط', nav_cards='Flashcards للمراجعة',
    edition='{src} AUDIO → AR NOTES', play='شغّل الفيديو على YouTube', thumb_alt='صورة الفيديو', asof='الأرقام زي ما كانت على YouTube يوم {d}.',
    watch='شوف الفيديو', channel='القناة على YouTube', sections='الأقسام', in_guide='محتوى الدليل', progress='تقدّمك',
    how='<b>طريقة القراءة:</b> كل قسم معلّم بلون مستواه، وزرار <span class="ts" style="padding:0 7px"><span aria-hidden="true">▶</span> 00:00</span> بيفتح الفيديو على نفس الجزء.',
    quick_note='الوضع السريع شغّال: بتشوف خلاصة كل قسم بس. اقفله من نفس الزرار علشان ترجع للشرح الكامل.',
    lead1='المصدر: نص الترجمة بتاع الفيديو. الأمثلة والأرقام من كلام المتحدث، وأي إضافة من عندي مكتوب جنبها <b>(ملاحظة الشارح)</b>.',
    lead2='المصطلحات التقنية سايبها بالإنجليزي زي ما هي، علشان تعرف تدوّر عليها.',
    views='مشاهدة', likes='لايك', comments='كومنت', published='تاريخ النشر', f_ch='فصل في الفيديو', f_sec='أقسام شرح', f_cards='كارت مراجعة',
    ch_lvl='VIDEO · فصول الفيديو', ch_sm='{n} فصل زي ما صاحب القناة حاطهم في وصف الفيديو. دوس على أي فصل علشان تفتح الفيديو عليه.',
    res_lvl='LINKS · المصادر', res_sm='الروابط دي من وصف الفيديو نفسه.', res_refs='مراجع', res_more='فيديوهات تانية من نفس القناة', res_follow='تابع المتحدث',
    cards_lvl='PRACTICE · مراجعة', cards_sm='اقرا السؤال وجاوب في دماغك، وبعدين اقلب الكارت. <kbd>Space</kbd> بتقلب، والأسهم بتنقلك. "لسه" بترجّعلك الكارت بعد شوية.',
    search='دوّر في الدليل (مثلًا Sharding)', filter='فلتر حسب القسم', prev='→ السابق', next='التالي ←', know='عرفتها', again='لسه', shuffle='لخبط الترتيب',
    anki='نفس الكروت موجودة كملف Anki جنب الدليل على جهازك: <code>{f}</code>. علشان تستورده افتح Anki واختار File ثم Import.',
    footer='<p><b>عن الدليل ده:</b> ملخص دراسي <b>غير رسمي</b> ومش تابع للقناة. معمول من ترجمة فيديو <a href="{u}" target="_blank" rel="noopener">{t}</a> بتاع {c}. الأفكار والأمثلة حق صاحبها، والصورة والفيديو ملك القناة.</p><p>اتعمل يوم {d}.</p>',
    L=dict(q='سؤال', a='الإجابة', hintQ='دوس علشان تشوف الإجابة', hintA='دوس تاني علشان تخفي الإجابة', all='الكل',
           allLv='كل المستويات', done='خلصت القسم ده', doneOn='خلصته', srs='{due} كارت مستحق للمراجعة النهارده · {learned} من {t} اتثبتوا', noHits='مفيش نتايج', rtl=True)),
 'en': dict(
    marks=dict(contents='Contents', kt='Key takeaways:', mx='Common mistakes:', ans='Answer:', note="(Explainer's note)"),
    diff=dict(basic='Easy', mid='Medium', adv='Hard'), kt='Key takeaways', mx='Common mistakes', ans_sum='Show answer', quiz='Your scenario score:', retry='Try again',
    rt=lambda m: f'{m} min read', wpm=220,
    done='Mark as done', done_on='Done', quick='Quick mode', tldr_lvl='TL;DR · IN A HURRY', tldr_sm='The key points of the whole video, in minutes',
    groups=dict(start='Start here', ov='Overview', basic='Basics', mid='Intermediate', adv='Advanced', bonus='Bonus', ref='Reference & review'),
    lv=None, nav_ch='Official video chapters', nav_res='Resources and links', nav_cards='Review flashcards',
    edition='ENGLISH EDITION', play='Play the video on YouTube', thumb_alt='Video thumbnail', asof='Figures as shown on YouTube on {d}.',
    watch='Watch the video', channel='Channel on YouTube', sections='Sections', in_guide='In this guide', progress='Your progress',
    how='<b>How to read:</b> each section carries its level colour, and the <span class="ts" style="padding:0 7px"><span aria-hidden="true">▶</span> 00:00</span> button opens the video at that point.',
    quick_note='Quick mode is on: you see only each section\'s key takeaways. Use the same switch to return to the full explanation.',
    lead1="Source: the video's subtitles. Examples and numbers come from the speaker; anything I added is marked <b>(Explainer's note)</b>.",
    lead2='Other language editions are one click away in the language switch.',
    views='views', likes='likes', comments='comments', published='published', f_ch='video chapters', f_sec='guide sections', f_cards='flashcards',
    ch_lvl='VIDEO · CHAPTERS', ch_sm='All {n} chapters as listed in the video description. Pick one to open the video there.',
    res_lvl='LINKS · RESOURCES', res_sm='Every link here comes from the video description.', res_refs='References', res_more='More from the same channel', res_follow='Follow the speaker',
    cards_lvl='PRACTICE · REVIEW', cards_sm='Answer in your head, then flip the card. <kbd>Space</kbd> flips; arrow keys move. "Again" brings the card back a little later.',
    search='Search the guide (e.g. sharding)', filter='Filter by topic', prev='← Previous', next='Next →', know='Got it', again='Again', shuffle='Shuffle',
    anki='The same cards are saved next to this guide as an Anki deck: <code>{f}</code>. To import it, open Anki and choose File, then Import.',
    footer='<p><b>About this guide:</b> an <b>unofficial</b> study guide, not affiliated with the channel. Built from the subtitles of <a href="{u}" target="_blank" rel="noopener">{t}</a> by {c}. The ideas and examples are the speaker\'s; the thumbnail and video belong to the channel.</p><p>Made on {d}.</p>',
    L=dict(q='Question', a='Answer', hintQ='Click to reveal the answer', hintA='Click again to hide the answer', all='All',
           allLv='All levels', done='Mark as done', doneOn='Done', srs='{due} cards due for review today · {learned} of {t} learned', noHits='No results', rtl=False)),
}
LANG_LABEL = {'ar': 'عربي', 'en': 'English'}


# ---- concept visuals: ```loop / ```matrix / ```spectrum fences (syntax in references/guide-format.md) ----
def _fields(src):
    """'key: value' lines and '- label: detail' items (a leading '*' marks the highlighted item)."""
    keys, items = {}, []
    for line in src.strip().splitlines():
        line = line.strip()
        if line.startswith('- '):
            body = line[2:].strip(); star = body.startswith('*')
            label, _, detail = body.lstrip('* ').partition(':')
            items.append((label.strip(), detail.strip(), star))
        elif ':' in line:
            k, _, v = line.partition(':'); keys[k.strip()] = v.strip()
    return keys, items


def visual_loop(src, n):
    """A cycle of 2–6 stages with a travelling dot; each stage lights up as the dot passes; optional exit box."""
    k, items = _fields(src)
    stages = items[:6]; N = len(stages); cx, cy, r, dur = 200, 150, 105, 2 * N
    pos = [(cx + r * math.sin(-2 * math.pi * i / N), cy - r * math.cos(2 * math.pi * i / N)) for i in range(N)]
    e = html.escape; g = []
    for i, ((label, detail, _), (x, y)) in enumerate(zip(stages, pos)):
        c = i / N
        if i == 0:
            kt, vals = f'0;{0.6 / N:.3f};{1 - 0.25 / N:.3f};1', '1;0;0;1'
        else:
            kt, vals = f'0;{c - 0.25 / N:.3f};{c:.3f};{c + 0.4 / N:.3f};1', '0;0;1;0;0'
        g.append(f'<g><circle cx="{x:.0f}" cy="{y:.0f}" r="34" class="rl-glow"><animate attributeName="opacity" values="{vals}" keyTimes="{kt}" dur="{dur}s" repeatCount="indefinite"/></circle>'
                 f'<circle cx="{x:.0f}" cy="{y:.0f}" r="27" class="rl-n"/><text x="{x:.0f}" y="{y - 2:.0f}" class="rl-t" text-anchor="middle">{e(label)}</text>'
                 f'<text x="{x:.0f}" y="{y + 14:.0f}" class="rl-s" text-anchor="middle">{e(detail)}</text></g>')
    exit_svg = ''
    if k.get('exit'):
        lx, ly = pos[-1]; label, _, detail = k['exit'].partition(':'); bx, by = 396, min(max(ly - 24, 20), 236)
        exit_svg = (f'<path d="M{lx + 28:.0f},{ly:.0f} C{(lx + bx) / 2:.0f},{ly + 10:.0f} {(lx + bx) / 2:.0f},{by + 24:.0f} {bx - 4},{by + 24:.0f}" class="rl-exit" marker-end="url(#ah{n})"/>'
                    f'<rect x="{bx}" y="{by}" width="140" height="48" rx="12" class="rl-final"/>'
                    f'<text x="{bx + 70}" y="{by + 22}" class="rl-t" text-anchor="middle">{e(label.strip())}</text>'
                    f'<text x="{bx + 70}" y="{by + 39}" class="rl-s" text-anchor="middle">{e(detail.strip())}</text>')
        if k.get('done'):
            exit_svg += f'<text x="{(lx + 28 + bx) / 2:.0f}" y="{min(ly, by + 24) - 16:.0f}" class="rl-small" text-anchor="middle">{e(k["done"])}</text>'
    again = f'<text x="{cx + 100}" y="{cy - 64}" class="rl-small" text-anchor="middle">{e(k["again"])}</text>' if k.get('again') else ''
    path = f'M{cx},{cy - r} A{r},{r} 0 1,0 {cx + 0.01},{cy - r}'
    return (f'<figure class="diagram loopfig" role="img" aria-label="{e(k.get("center", ""))}: {e(" → ".join(x[0] for x in stages))}">'
            f'<svg viewBox="0 0 560 300" width="100%" style="max-width:560px;display:block;margin:0 auto">'
            f'<defs><marker id="ah{n}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="rl-ahf"/></marker></defs>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" class="rl-ring"/><circle cx="{cx}" cy="{cy}" r="{r}" class="rl-flow"/>{exit_svg}{again}{"".join(g)}'
            f'<circle r="6" class="rl-dot"><animateMotion dur="{dur}s" repeatCount="indefinite" path="{path}"/></circle>'
            f'<text x="{cx}" y="{cy + 6}" class="rl-mid" text-anchor="middle">{e(k.get("center", ""))}</text></svg>'
            + (f'<figcaption>{e(k["caption"])}</figcaption>' if k.get('caption') else '') + '</figure>')


def visual_matrix(src, n):
    """A 2×2 quadrant: x/y axis labels as 'low | high', four cells in reading order; '*' highlights, '—' marks an empty cell."""
    k, items = _fields(src); e = html.escape
    xs = [x.strip() for x in k.get('x', '|').split('|')]; ys = [y.strip() for y in k.get('y', '|').split('|')]
    def cell(it):
        label, detail, star = it
        if label in ('—', '-', ''):
            return '<div class="mx-cell dim"></div>'
        return f'<div class="mx-cell{" star" if star else ""}"><b>{e(label)}</b>' + (f'<span>{e(detail)}</span>' if detail else '') + '</div>'
    cells = (items + [('—', '', False)] * 4)[:4]
    return (f'<div class="matrix" role="table" aria-label="{e(k.get("title", "matrix"))}"><div></div><div class="mx-h">{e(xs[0])}</div><div class="mx-h">{e(xs[-1])}</div>'
            f'<div class="mx-v">{e(ys[0])}</div>{cell(cells[0])}{cell(cells[1])}<div class="mx-v">{e(ys[-1])}</div>{cell(cells[2])}{cell(cells[3])}</div>')


def visual_spectrum(src, n):
    """Points along one axis, ends first and last; '*' highlights the recommended point."""
    _, items = _fields(src); e = html.escape
    cols = ''.join(f'<div class="{"mid" if star else ""}"><b>{e(label)}</b><span>{e(detail)}</span></div>' for label, detail, star in items)
    return f'<div class="spectrum"><div class="sp-bar"></div><div class="sp-labels" style="grid-template-columns:repeat({len(items)},1fr)">{cols}</div></div>'


def _num(v):
    """Midpoint of '5–10' / '15-20' / '15' → float; None when there is no number."""
    nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', v)]
    return sum(nums[:2]) / len(nums[:2]) if nums else None


def visual_timeline(src, n):
    """Steps with a time budget, drawn to scale; 'rest' takes whatever is left of 'total'."""
    k, items = _fields(src); e = html.escape; unit = k.get('unit', '')
    vals = [_num(d) for _, d, _ in items]
    known = sum(v for v in vals if v)
    total = _num(k.get('total', '')) or known
    rest = max(total - known, total * 0.06) if total else 1
    segs = ''
    for i, ((label, detail, star), v) in enumerate(zip(items, vals)):
        w = v if v else rest
        txt = f'{detail} {unit}'.strip() if v else detail
        segs += (f'<div class="tl-seg{" star" if star else ""}" style="flex-grow:{w:.2f};--i:{i}"><span class="tl-n">{i + 1}</span>'
                 f'<b>{e(label)}</b><span class="tl-d">{e(txt)}</span></div>')
    head = f'<div class="tl-head"><span>{e(k.get("title", ""))}</span><span>{e(k.get("total", ""))} {e(unit)}</span></div>' if k.get('title') or k.get('total') else ''
    return f'<figure class="timeline" role="img" aria-label="{e(k.get("title", "timeline"))}">{head}<div class="tl-bar">{segs}</div></figure>'


def visual_calc(src, n):
    """Back-of-the-envelope maths as a chain of rows: 'a × b = result'; the result is highlighted."""
    k, items = _fields(src); e = html.escape
    rows = []
    for raw in [l.strip()[2:] for l in src.strip().splitlines() if l.strip().startswith('- ')]:
        left, eq, right = raw.rpartition('=')
        if not eq:
            left, right = raw, ''
        parts = re.split(r'\s+([×x÷/+−\-])\s+', left.strip())
        chips = ''.join(f'<span class="op">{e(t)}</span>' if t in '×x÷/+−-' else f'<span class="term">{e(t)}</span>' for t in parts if t)
        rows.append(f'<div class="calc-row" style="--i:{len(rows)}">{chips}' + (f'<span class="op">=</span><span class="cres">{e(right.strip())}</span>' if right else '') + '</div>')
    title = f'<figcaption class="calc-t">{e(k["title"])}</figcaption>' if k.get('title') else ''
    note = f'<p class="calc-note">{e(k["note"])}</p>' if k.get('note') else ''
    return f'<figure class="calc">{title}<div class="calc-rows" dir="ltr">{"".join(rows)}</div>{note}</figure>'


VISUALS = {'loop': visual_loop, 'matrix': visual_matrix, 'spectrum': visual_spectrum, 'timeline': visual_timeline, 'calc': visual_calc}

# Isolate Latin runs inside Arabic text so punctuation and word order render correctly.
TOK = r"[A-Za-z0-9][A-Za-z0-9_\-/.+&'’]*[A-Za-z0-9]|[A-Za-z]"
RUN = re.compile(rf"(?<![&#\w])(?:{TOK})(?:[  ]+(?:{TOK}))*")
SKIP = {'pre', 'code', 'script', 'style', 'svg', 'time'}


def bidi(h):
    out, skip = [], 0
    for p in re.split(r'(<[^>]+>)', h):
        if p.startswith('<'):
            m = re.match(r'<(/?)([a-zA-Z0-9]+)', p)
            if m and m[2].lower() in SKIP and not p.endswith('/>'):
                skip += -1 if m[1] else 1
            out.append(p)
        elif skip > 0 or not re.search('[A-Za-z]', p):
            out.append(p)
        else:
            out.append(RUN.sub(lambda r: f'<span class="lat" dir="ltr">{r[0]}</span>' if re.search('[A-Za-z]', r[0]) else r[0], p))
    return ''.join(out)


def compact(n):
    if n is None:
        return '—'
    for div, suf in ((1e9, 'B'), (1e6, 'M'), (1e3, 'K')):
        if n >= div:
            v = n / div
            return (f'{v:.1f}'.rstrip('0').rstrip('.') if v < 10 else f'{v:.0f}') + suf
    return str(n)


def short_url(u):
    return re.sub(r'^https?://(www\.)?', '', u).rstrip('/')[:48]


def fmt_date(d, lang):
    if lang == 'ar':
        return f'{d.day} {AR_MONTHS[d.month - 1]} {d.year}'
    return f'{EN_MONTHS[d.month - 1]} {d.day}, {d.year}'


def uri(path):
    p = Path(path)
    if not p.exists():
        return ''
    mime = 'image/png' if p.suffix == '.png' else 'image/jpeg'
    return f'data:{mime};base64,' + base64.b64encode(p.read_bytes()).decode()


def glossary_terms(md, levels):
    """(term, definition) pairs from the table in the section marked {glossary}."""
    title = next((t for t, a in levels.items() if a == 'glossary'), None)
    m = title and re.search(rf'^## {re.escape(title)}\n(.*?)(?=^## |\Z)', md, flags=re.S | re.M)
    pairs = []
    for row in re.findall(r'^\|(.+)\|\s*$', m[1], flags=re.M)[2:] if m else []:  # skip header + separator rows
        cells = [c.strip() for c in row.split('|')]
        term = re.sub(r'\s*\(.*?\)\s*$', '', re.sub(r'\*\*|`', '', cells[0])).strip()
        dfn = re.sub(r'\*\*|`', '', cells[1]).strip() if len(cells) > 1 else ''
        if term and dfn:
            pairs.append((term, dfn))
    return pairs


TIP_SKIP = {'h1', 'h2', 'h3', 'h4', 'a', 'code', 'pre', 'summary', 'button', 'th', 'dfn', 'script', 'style', 'svg', 'time'}


def add_tips(h, terms):
    """Wrap the first use of each glossary term in this chunk with a hover/focus definition."""
    rx = re.compile(r'(?<![\w-])(' + '|'.join(re.escape(t) for t, _ in sorted(terms, key=lambda x: -len(x[0]))) + r')(?![\w-])', re.I)
    defs = {t.lower(): d for t, d in terms}
    out, skip, used = [], 0, set()

    def wrap(m):
        k = m[1].lower()
        if k in used:
            return m[0]
        used.add(k)
        return f'<dfn class="gt" tabindex="0" data-def="{html.escape(defs[k], quote=True)}">{m[1]}</dfn>'
    for p in re.split(r'(<[^>]+>)', h):
        if p.startswith('<'):
            m = re.match(r'<(/?)([a-zA-Z0-9]+)', p)
            if m and m[2].lower() in TIP_SKIP and not p.endswith('/>'):
                skip += -1 if m[1] else 1
            out.append(p)
        else:
            out.append(p if skip > 0 else rx.sub(wrap, p))
    return ''.join(out)


def render_body(md, lang):
    U = UI[lang]; M = U['marks']; iso = bidi if lang in RTL else (lambda h: h)
    md = re.sub(rf'## {re.escape(M["contents"])}\n.*?\n---\n', '', md, flags=re.S)
    md = md.split('\n---\n', 1)[1]  # drop the title block
    levels = {}

    def head_attr(m):  # "## 1. Title {basic}" -> level map; braces never reach the page
        title, attr = m[1].strip(), m[2].strip()
        levels[title] = attr
        return f'## {title}'
    md = re.sub(r'^## (.*?)[ \t]*\{([a-z]+)\}[ \t]*$', head_attr, md, flags=re.M)
    terms = glossary_terms(md, levels)
    # question difficulty: "1. Question? {mid}" -> a pill at the end of the question
    md = re.sub(r'^([ \t]*\d+\. .*?)[ \t]*\{(basic|mid|adv)\}[ \t]*$', lambda m: f'{m[1]} <span class="qlv qlv-{m[2]}">{U["diff"][m[2]]}</span>', md, flags=re.M)

    blocks = {}
    def ph(key, h):
        blocks[key] = h
        return f'\n\nPH{key}PH\n\n'
    out, buf, fl, n = [], None, '', 0
    for line in md.split('\n'):
        if buf is None and line.startswith('```'):
            buf, fl = [], line[3:].strip(); continue
        if buf is not None and line.strip() == '```':
            n += 1; f = '\n'.join(buf)
            if fl == 'mermaid':
                out.append(ph(f'B{n}', f'<figure class="diagram"><pre class="mermaid">{html.escape(f.strip())}</pre></figure>'))
            elif fl == 'html':
                out.append(ph(f'B{n}', f))
            elif fl in VISUALS:
                out.append(ph(f'B{n}', VISUALS[fl](f, n)))
            else:
                out.append('```' + fl + '\n' + f + '\n```')
            buf = None; continue
        (buf if buf is not None else out).append(line)
    md = '\n'.join(out)

    def boxed(marker, cls, title):
        def f(m):
            items = ''.join('<li>' + markdown.markdown(x[4:])[3:-4] + '</li>' for x in m[1].strip('\n').split('\n'))
            return ph(f'{cls}{len(blocks)}', f'<aside class="{cls}"><div class="{cls}-h"><span aria-hidden="true">◆</span> {title}</div><ul>{items}</ul></aside>')
        return re.compile(rf'> \*\*{re.escape(marker)}\*\*\n>\n((?:> - .*\n)+)'), f
    for marker, cls, title in ((M['kt'], 'kt', U['kt']), (M['mx'], 'mx', U['mx'])):
        rx, f = boxed(marker, cls, title)
        md = rx.sub(f, md)

    body = markdown.markdown(md, extensions=['tables', 'fenced_code', 'sane_lists'])
    for k, v in blocks.items():
        body = body.replace(f'<p>PH{k}PH</p>', v)
    body = re.sub(r'<p>▶️ <a href="([^"]+)">([^<]+)</a></p>', r'<a class="ts" href="\1" target="_blank" rel="noopener"><span aria-hidden="true">▶</span> \2</a>', body)
    body = body.replace('<table>', '<div class="tbl"><table>').replace('</table>', '</table></div>').replace('<hr />', '')
    body = re.sub(rf'<blockquote>(\s*<p>(?:<strong>)?{re.escape(M["note"])})', r'<blockquote class="note">\1', body)

    # scenario MCQ: "- [ ] wrong" / "- [x] right" list, then the Answer paragraph as the explanation
    def mcq(m):
        opts = re.findall(r'<li>\[([ xX])\]\s*(.*?)</li>', m[0], flags=re.S)
        return '<div class="mcq">' + ''.join(f'<button class="opt" type="button" data-ok="{1 if o.strip() else 0}">{t}</button>' for o, t in opts) + '</div>'
    body = re.sub(r'<ul>\s*(?:<li>\[[ xX]\].*?</li>\s*)+</ul>', mcq, body, flags=re.S)
    ans = re.escape(M['ans'])
    body = re.sub(rf'(<div class="mcq">.*?</div>)\s*<p><strong>{ans}</strong>\s*(.*?)</p>', r'\1<div class="mcq-exp" hidden><p>\2</p></div>', body, flags=re.S)
    body = re.sub(rf'<p><strong>{ans}</strong>\s*(.*?)</p>', rf'<details class="ans"><summary>{U["ans_sum"]}</summary><p>\1</p></details>', body, flags=re.S)

    toc, gloss = [], []
    def h2(m):
        t = m[1]; plain = re.sub(r'<[^>]+>', '', t); num = re.match(r'(\d+)\.', t)
        lv = levels.get(plain.strip(), '')
        if lv == 'glossary':
            lv = 'ref'; gloss.append(f'sec-{num[1]}' if num else f'sec-x{len(toc)}')
        i = 'tldr' if lv == 'tldr' else (f'sec-{num[1]}' if num else f'sec-x{len(toc)}')
        toc.append((i, plain, lv)); return f'<h2 id="{i}">{t}</h2>'
    body = re.sub(r'<h2>(.*?)</h2>', h2, body)
    lvl_of = {i: lv for i, _, lv in toc}

    def sect(p):
        m = re.match(r'<h2 id="([^"]+)">(.*?)</h2>\s*(<a class="ts".*?</a>)?', p, flags=re.S)
        if not m:
            return p
        i, title, ts = m[1], m[2], m[3] or ''
        if i == 'tldr':
            title = re.sub(r'^⚡\s*', '', title)
            head = (f'<header class="sh"><span class="sn" aria-hidden="true">⚡</span><div class="st"><span class="lvl"><span class="dot"></span>{U["tldr_lvl"]}</span>'
                    f'<h2 id="tldr">{title}</h2><div class="sm"><span>{U["tldr_sm"]}</span>'
                    f'<button class="qbtn" type="button" aria-pressed="false"><span class="sw" aria-hidden="true"></span>{U["quick"]}</button></div></div></header>')
            return '<section class="sec lv-ov tldr first">' + head + p[m.end():] + '</section>'
        lv = lvl_of.get(i) if lvl_of.get(i) in LEVELS else 'ov'
        num = re.match(r'(\d+)\.\s*(.*)', title, flags=re.S)
        n_txt, title = (f'{int(num[1]):02d}', num[2]) if num else ('•', title)
        lesson = lv != 'ref'
        done = (f'<button class="done" type="button" data-id="{i}" aria-pressed="false"><span class="ck" aria-hidden="true"></span>{U["done"]}</button>' if lesson else '')
        mins = max(1, round(len(re.sub(r'<[^>]+>', ' ', p).split()) / U['wpm']))
        lvl = f'<bdi>{LV_EN[lv]}</bdi> · {U["lv"][lv]}' if U['lv'] else LV_EN[lv]
        head = (f'<header class="sh"><span class="sn" aria-hidden="true">{n_txt}</span><div class="st"><span class="lvl"><span class="dot"></span>{lvl}</span>'
                f'<h2 id="{i}">{title}</h2><div class="sm"><span>{U["rt"](mins)}</span>{ts}{done}</div></div></header>')
        rest = p[m.end():]
        if 'class="mcq"' in rest:
            head += f'<div class="quiz-score"><span>{U["quiz"]}</span><b class="qs">0 / 0</b><button class="btn qreset" type="button">{U["retry"]}</button></div>'
        return f'<section class="sec lv-{lv}{" lesson" if lesson else ""}{" glossary" if i in gloss else ""}">' + head + rest + '</section>'
    body = ''.join(sect(p) for p in re.split(r'(?=<h2 id=)', body))
    body = re.sub(r'<h3>(\d+\.\d+)\s+(.*?)</h3>\s*(<a class="ts".*?</a>)?', lambda m: f'<h3 id="s{m[1].replace(".", "-")}"><span class="hn">{m[1]}</span><span class="ht">{m[2]}</span>{m[3] or ""}</h3>', body, flags=re.S)
    body = re.sub(r'<h4>(.*?)</h4>\s*(<a class="ts".*?</a>)', r'<h4><span class="ht">\1</span>\2</h4>', body, flags=re.S)
    if terms:
        body = ''.join(p if any(f'id="{g}"' in p[:600] for g in gloss) else add_tips(p, terms) for p in re.split(r'(?=<section )', body))
    body = iso(body)
    if not re.search(r'class="(?:diagram loopfig|matrix|spectrum|timeline|calc)"', body):
        print(f'warning [{lang}]: no concept visual (loop/matrix/spectrum/timeline/calc); the quality bar expects at least two', file=sys.stderr)
    tldr = ''
    mt = re.search(r'<section class="sec lv-ov tldr first">.*?</section>', body, flags=re.S)
    if mt:
        tldr = mt[0]; body = body.replace(tldr, '', 1)
    return tldr, body, toc


def place_chapters(chapters, md, cmap):
    """Put each description chapter on the caption-accurate time of the guide heading it maps to.

    Description timestamps are typed by hand and can drift from the speech by minutes;
    guide.json chapter_map ({"Chapter title": "3" or "3.2"}) points a chapter at the
    `## 3.` / `### 3.2` heading whose ▶️ link came from the spoken words. Unmapped
    chapters keep the description time."""
    heads, cur = {}, None
    for line in md.splitlines():
        h = re.match(r'^#{2,3} (\d+(?:\.\d+)?)[. ]', line)
        if h:
            cur = h[1]; continue
        t = re.match(r'^▶️ \[\d+:\d+\]\([^)]*?[?&]t=(\d+)s\)', line)
        if t and cur and cur not in heads:
            heads[cur] = int(t[1])
    missing = [k for k, v in cmap.items() if v not in heads]
    if missing:
        sys.exit(f'chapter_map points at headings with no ▶️ time: {missing}')
    return [{**c, 'start_time': heads[cmap[c['title']]]} if c['title'] in cmap else c for c in chapters]


def build(gdir, out, standalone=False):
    G = json.loads((gdir / 'guide.json').read_text())
    V = json.loads((gdir / 'meta/video.json').read_text())
    related = json.loads((gdir / 'meta/related.json').read_text()) if (gdir / 'meta/related.json').exists() else []
    langs = G['langs']; vid = V['id']; vurl = f'https://www.youtube.com/watch?v={vid}'
    today = date.today(); up = V.get('upload_date') or ''
    pub = date(int(up[:4]), int(up[4:6]), int(up[6:])) if len(up) == 8 else None
    img = {k: uri(gdir / 'meta' / f) for k, f in (('thumb', 'thumb.jpg'), ('avatar', 'avatar.jpg'), ('banner', 'banner.jpg'))}
    chapters = place_chapters(V.get('chapters') or [], (gdir / f'guide.{langs[0]}.md').read_text(), G.get('chapter_map', {})) if G.get('show_chapters', True) else []
    ch_items = ''.join(f'<li><a href="{vurl}&amp;t={int(c["start_time"])}s" target="_blank" rel="noopener"><time>{int(c["start_time"]) // 60:02d}:{int(c["start_time"]) % 60:02d}</time>'
                       f'<span class="en">{html.escape(c["title"])}</span></a></li>' for c in chapters)
    tpl = (ASSETS / 'wrap.html').read_text()
    wraps, data = [], {'id': vid, 'langs': langs}
    for ix, lang in enumerate(langs):
        U = UI[lang]; iso = bidi if lang in RTL else (lambda h: h); P = '' if ix == 0 else f'{lang}-'
        tldr, body, toc = render_body((gdir / f'guide.{lang}.md').read_text(), lang)
        cards = []
        cfile = gdir / f'cards.{lang}.txt'
        for line in cfile.read_text().splitlines():
            if line.startswith('#') or not line.strip():
                continue
            q, a, tag = (line.split('\t') + ['', ''])[:3]
            cards.append({'q': iso(q), 'a': iso(a), 't': tag, 'l': G.get('card_levels', {}).get(tag, '')})
        tags = G.get('card_tags', {}).get(lang) or {t: t for t in dict.fromkeys(c['t'] for c in cards)}
        data[lang] = {'cards': cards, 'tags': tags, 'diff': U['diff'], 'L': U['L']}

        def item(i, label, num=''):
            return f'<li><a href="#{i}"><span class="nn">{num}</span><span>{iso(html.escape(label))}</span></a></li>'
        T = {i: re.sub(r'^\d+\.\s*', '', t) for i, t, _ in toc}
        nums = {i: (re.match(r'(\d+)\.', t)[1] if re.match(r'(\d+)\.', t) else '•') for i, t, _ in toc}
        start = ([item('tldr', T['tldr'].lstrip('⚡ '), '⚡')] if 'tldr' in T else []) + ([item('chapters', U['nav_ch'], '▸')] if chapters else [])
        groups = [('start', 'ov', start)]
        for i, _, lv in toc:
            if i == 'tldr':
                continue
            lv = lv if lv in LEVELS else 'ov'
            key = 'start' if lv == 'ov' else lv
            if groups[-1][0] != key:
                groups.append((key, lv, []))
            groups[-1][2].append(item(i, T[i], nums[i]))
        tail = ([item('resources', U['nav_res'], '↗')] if (G.get('resources') or related or G.get('socials')) else []) + [item('cards', U['nav_cards'], '✦')]
        if groups[-1][0] == 'ref':
            groups[-1][2].extend(tail)
        else:
            groups.append(('ref', 'ref', tail))
        nav = ''.join(f'<li class="grp lv-{lv}"><span class="gl"><span class="dot"></span>{U["groups"][key]}</span><ol>{"".join(it)}</ol></li>' for key, lv, it in groups if it)

        stats = (f'<div><b>{compact(V.get("view_count"))}</b><span>{U["views"]}</span></div><div><b>{compact(V.get("like_count"))}</b><span>{U["likes"]}</span></div>'
                 f'<div><b>{compact(V.get("comment_count"))}</b><span>{U["comments"]}</span></div>'
                 f'<div><b class="ar">{fmt_date(pub, lang) if pub else "—"}</b><span>{U["published"]}</span></div>')
        n_sec = sum(1 for i, _, _ in toc if i.startswith('sec-'))
        facts = (f'<span><b>{len(chapters)}</b> {U["f_ch"]}</span>' if chapters else '') + f'<span><b>{n_sec}</b> {U["f_sec"]}</span><span><b>{len(cards)}</b> {U["f_cards"]}</span>'
        ch_sec = ''
        if chapters:
            ch_sec = (f'<section class="sec lv-ov"><header class="sh"><span class="sn" aria-hidden="true">▸</span><div class="st"><span class="lvl"><span class="dot"></span>{U["ch_lvl"]}</span>'
                      f'<h2 id="chapters">{U["nav_ch"]}</h2><div class="sm"><span>{U["ch_sm"].format(n=len(chapters))}</span></div></div></header>'
                      f'<ol class="chap" dir="ltr" lang="en">{ch_items}</ol></section>')
        res = ''
        if G.get('resources') or related or G.get('socials'):
            res = (f'<section class="sec lv-ref"><header class="sh"><span class="sn" aria-hidden="true">↗</span><div class="st"><span class="lvl"><span class="dot"></span>{U["res_lvl"]}</span>'
                   f'<h2 id="resources">{U["nav_res"]}</h2><div class="sm"><span>{U["res_sm"]}</span></div></div></header>')
            if G.get('resources'):
                res += f'<h3 class="sub3">{U["res_refs"]}</h3><div class="res-grid">' + ''.join(
                    f'<a class="res" href="{html.escape(r["url"])}" target="_blank" rel="noopener"><small>{html.escape(r.get("kicker", {}).get(lang, ""))}</small>'
                    f'<b dir="auto">{html.escape(r["title"])}</b><span>{iso(html.escape(r.get("note", {}).get(lang, "")))}</span>'
                    f'<span class="url">{html.escape(short_url(r["url"]))}</span></a>' for r in G['resources']) + '</div>'
            if related:
                res += f'<h3 class="sub3">{U["res_more"]}</h3><div class="res-grid">' + ''.join(
                    f'<a class="res vid" dir="ltr" lang="en" href="https://www.youtube.com/watch?v={r["id"]}" target="_blank" rel="noopener"><img src="{uri(gdir / "meta" / ("rel_" + r["id"] + ".jpg"))}" alt="" loading="lazy">'
                    f'<div class="in"><b>{html.escape(r["title"])}</b><span>{r.get("duration", "")} · {compact(r.get("views"))} views</span></div></a>' for r in related) + '</div>'
            if G.get('socials'):
                res += f'<h3 class="sub3">{U["res_follow"]}</h3><div class="social">' + ''.join(
                    f'<a class="lnk" href="{html.escape(s["url"])}" target="_blank" rel="noopener">{iso(html.escape(s["label"]))}</a>' for s in G['socials']) + '</div>'
            res += '</section>'
        foot = U['footer'].format(u=vurl, t=html.escape(V['title']), c=html.escape(V.get('channel', '')), d=fmt_date(today, lang)) + G.get('footer_extra', {}).get(lang, '')
        tags_html = ''.join(f'<span>#{re.sub(r"[^A-Za-z0-9]", "", t.title() if " " in t else t)}</span>' for t in (G.get('tags') or V.get('tags') or [])[:5])
        verified = ('<svg width="15" height="15" viewBox="0 0 24 24" role="img" aria-label="verified"><circle cx="12" cy="12" r="10" fill="var(--muted)"/>'
                    '<path d="M7.5 12.3l3 3 6-6.3" fill="none" stroke="var(--surface)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>') if V.get('channel_is_verified') else ''
        handle = ' · '.join(x for x in (V.get('uploader_id') or '', f'{compact(V.get("channel_follower_count"))} subscribers' if V.get('channel_follower_count') else '') if x)
        rep = {
            'DIR': 'rtl' if lang in RTL else 'ltr', 'LANG': lang, 'HIDDEN': ' hidden' if ix else '', 'CATEGORY': html.escape(((V.get('categories') or ['VIDEO'])[0]).upper()),
            'EDITION': U['edition'].format(src=(V.get('language') or 'en').split('-')[0].upper()), 'VIDEO_URL': vurl, 'IMG_THUMB': img['thumb'], 'IMG_AVATAR': img['avatar'], 'DURATION': V.get('duration_string', ''),
            'BANNER_STYLE': f' style="background-image:url(\'{img["banner"]}\')"' if img['banner'] else '',
            'STATS': stats, 'ORIG': f'<p class="orig" dir="ltr" lang="en">{html.escape(V["title"])}</p>', 'H1': iso(html.escape(G['h1'][lang])),
            'H1_EM': iso(html.escape(G.get('h1_em', {}).get(lang, ''))), 'SUB': iso(html.escape(G['sub'][lang])), 'FACTS': facts,
            'CHANNEL': html.escape(V.get('channel', '')), 'VERIFIED': verified, 'HANDLE': html.escape(handle), 'ROLE': iso(html.escape(G.get('speaker_role', {}).get(lang, ''))),
            'CHANNEL_URL': V.get('channel_url', vurl), 'TAGS': tags_html, 'NAV': nav, 'TLDR': tldr, 'CHAPTERS_SECTION': ch_sec, 'BODY': body,
            'RESOURCES_SECTION': res, 'FOOTER': foot,
        }
        t_keys = dict(play=U['play'], thumb_alt=U['thumb_alt'], asof=U['asof'].format(d=fmt_date(today, lang)), watch=U['watch'], channel=U['channel'],
                      sections=U['sections'], in_guide=U['in_guide'], progress=U['progress'], quick=U['quick'], how=U['how'], quick_note=U['quick_note'],
                      lead1=U['lead1'], lead2=U['lead2'] if len(langs) > 1 or lang in RTL else '', cards_lvl=U['cards_lvl'], cards_h=U['nav_cards'],
                      cards_sm=U['cards_sm'], search=U['search'], filter=U['filter'], prev=U['prev'], next=U['next'], know=U['know'], again=U['again'], shuffle=U['shuffle'],
                      anki=iso(U['anki'].format(f=cfile.name)))
        w = re.sub(r'%%T_(\w+)%%', lambda m: t_keys[m[1]], tpl)
        w = re.sub(r'%%([A-Z0-9_]+)%%', lambda m: rep[m[1]], w)
        if P:  # unique ids per edition; data-id stays shared so progress is shared
            w = re.sub(r'(?<![\w-])id="([^"]+)"', rf'id="{P}\1"', w)
            w = re.sub(r'href="#([^"]+)"', rf'href="#{P}\1"', w)
            w = re.sub(r'url\(#([^)]+)\)', rf'url(#{P}\1)', w)
        wraps.append(w)
    sw = ''
    if len(langs) > 1:
        sw = '<div class="langsw" role="group" aria-label="Language">' + ''.join(
            f'<button type="button" data-l="{l}" lang="{l}" aria-pressed="{str(i == 0).lower()}">{LANG_LABEL.get(l, l)}</button>' for i, l in enumerate(langs)) + '</div>'
    page = (f'<title>{html.escape(G["page_title"])}</title>\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&family=Noto+Kufi+Arabic:wght@500;700;800&display=swap">\n'
            f'<style>\n{(ASSETS / "guide.css").read_text()}</style>\n<div class="progress" aria-hidden="true"><i id="prog"></i></div>\n{sw}\n'
            + '\n'.join(wraps)
            + '\n<button class="totop" id="totop" type="button" aria-label="Back to top">↑</button>\n<script>\n'
            + (ASSETS / 'guide.js').read_text().replace('%%DATA%%', json.dumps(data, ensure_ascii=False)) + '</script>\n')
    if standalone:
        page = (f'<!doctype html>\n<html lang="{langs[0]}">\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
                '<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n' + page
                + '<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>\n'
                  "<script>mermaid.initialize({startOnLoad:true,theme:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'default'})</script>\n</html>\n")
    left = re.findall(r'%%[A-Za-z0-9_]+%%', page)
    if left:
        sys.exit(f'unfilled placeholders: {sorted(set(left))}')
    out.write_text(page)
    print(f'{out}  {len(page) // 1024} KB  langs={",".join(langs)}  cards={[len(data[l]["cards"]) for l in langs]}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    gdir = Path(sys.argv[1]).expanduser().resolve()
    out = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else gdir / 'guide.html'
    build(gdir, out, '--standalone' in sys.argv)
