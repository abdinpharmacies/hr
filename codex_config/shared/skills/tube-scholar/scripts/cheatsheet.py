#!/usr/bin/env python3
"""Print a cheat sheet PDF per language from a built guide: the 5-minute summary, the decision
table, every calc/timeline/matrix/spectrum/loop visual and the glossary, on A4 in the light theme.

Usage: cheatsheet.py <guide-dir> [<guide.html>]
Writes <guide-dir>/cheatsheet.<lang>.pdf with headless Google Chrome.
"""
import re, shutil, subprocess, sys
from pathlib import Path

CHROME = next((p for p in ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', shutil.which('google-chrome') or '', shutil.which('chromium') or '') if p and Path(p).exists()), None)
PRINT = '''<style>
@page{size:A4;margin:12mm}
body{background:#fff!important;padding:0!important}
.wrap.cheat{display:block;max-width:none;font-size:12.5px;line-height:1.7}
.cheat .sh .sm,.cheat .ts,.cheat .done,.cheat .qbtn,.cheat .sn,.cheat .kt-h span{display:none!important}
.cheat .sh{border-bottom:2px solid var(--accent);margin:0 0 8px;padding-bottom:4px;display:block}
.cheat h1{font-size:22px;margin:0 0 2px}
.cheat .meta{color:var(--muted);font-size:11.5px;margin-bottom:14px}
.cheat main h2{font-size:17px;margin:0}
.cheat .sec{margin-top:16px;break-inside:auto}
.cheat .tldr>ol{grid-template-columns:1fr 1fr;gap:6px}
.cheat .tldr>ol>li{font-size:12px;padding:8px 10px;padding-inline-start:40px;box-shadow:none}
.cheat .tldr>ol>li::before{width:20px;height:20px;top:9px}
.cheat .tbl,.cheat .calc,.cheat .timeline,.cheat .spectrum,.cheat .matrix,.cheat .diagram{box-shadow:none;break-inside:avoid;margin:8px 0}
.cheat table{font-size:11.5px}.cheat th,.cheat td{padding:5px 8px}
.cheat .vis{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.cheat .vis>*{margin:0}
.cheat dfn.gt{border:0}
</style>'''


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if not CHROME:
        sys.exit('Google Chrome not found: skip the cheat sheet')
    gdir = Path(sys.argv[1]).expanduser().resolve()
    page = Path(sys.argv[2]).read_text() if len(sys.argv) > 2 else (gdir / 'guide.html').read_text()
    css = re.search(r'<style>(.*?)</style>', page, re.S)[1]
    title = re.search(r'<title>(.*?)</title>', page)[1]
    wraps = re.split(r'(?=<div class="wrap" dir=)', page)[1:]
    for w in wraps:
        w = w.split('<button class="totop"')[0]
        lang = re.search(r'data-lang="(\w+)"', w)[1]; d = re.search(r'dir="(\w+)"', w)[1]
        orig = re.search(r'<p class="orig"[^>]*>(.*?)</p>', w, re.S)
        chan = re.search(r'<div class="nm"[^>]*>(.*?)<', w, re.S)
        tldr = re.search(r'<section class="sec lv-ov tldr first">.*?</section>', w, re.S)
        vis = re.findall(r'<figure class="(?:diagram loopfig|timeline|calc)".*?</figure>|<div class="matrix".*?</div></div>|<div class="spectrum">.*?</div></div></div>', w, re.S)
        glos = re.search(r'<section class="sec lv-ref glossary">.*?</section>', w, re.S)
        body = (f'<h1>{title}</h1><div class="meta">{orig[1] if orig else ""} · {chan[1].strip() if chan else ""}</div>'
                + (tldr[0] if tldr else '') + (f'<section class="sec"><div class="vis">{"".join(vis)}</div></section>' if vis else '') + (glos[0] if glos else ''))
        html_file = gdir / f'.cheat.{lang}.html'
        html_file.write_text(f'<!doctype html><html data-theme="light" lang="{lang}" dir="{d}"><meta charset="utf-8"><title>{title}</title><style>{css}</style>{PRINT}'
                             f'<div class="wrap cheat" dir="{d}"><main>{body}</main></div></html>')
        pdf = gdir / f'cheatsheet.{lang}.pdf'
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--force-prefers-reduced-motion', '--virtual-time-budget=4000', '--no-pdf-header-footer',
                        f'--print-to-pdf={pdf}', f'file://{html_file}'], capture_output=True, timeout=180)
        html_file.unlink()
        pages = len(re.findall(rb'/Type\s*/Page[^s]', pdf.read_bytes())) if pdf.exists() else 0
        print(f'{lang}: {pdf.name} {pages} pages' if pdf.exists() else f'{lang}: PDF failed')


if __name__ == '__main__':
    main()
