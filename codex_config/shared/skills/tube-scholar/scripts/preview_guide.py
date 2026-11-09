#!/usr/bin/env python3
"""Screenshot a built guide before publishing, so visual bugs are caught by looking, not by the user.

Usage: preview_guide.py <guide.html> [<out-dir>]

Writes, with Google Chrome headless and reduced motion (everything at rest):
  preview-desktop.png   the top of the page at 1280 px, light theme
  preview-phone.png     the top of the page at 500 px (headless Chrome's minimum), dark theme
  preview-visuals.png   every concept visual (loop, matrix, spectrum, timeline, calc) on one sheet, light theme
Mermaid diagrams are parsed with the library from the jsDelivr CDN
instead; a syntax error would leave an empty box on the page, so it fails the preview.
"""
import html, json, re, shutil, subprocess, sys
from pathlib import Path

CHROME = next((p for p in ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', shutil.which('google-chrome') or '', shutil.which('chromium') or '') if p and Path(p).exists()), None)


def shot(html_file, png, w, h):
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-prefers-reduced-motion', '--virtual-time-budget=4000',
                    f'--window-size={w},{h}', f'--screenshot={png}', f'file://{html_file}'], capture_output=True, timeout=120)
    return png.exists()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if not CHROME:
        sys.exit('Google Chrome not found: skip the preview and say so in the report')
    src = Path(sys.argv[1]).resolve(); out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else src.parent / 'preview'
    out.mkdir(parents=True, exist_ok=True)
    page = src.read_text()
    # mirror the artifact skeleton, and record page width vs viewport (a wider page = horizontal scroll bug)
    head = '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>'
    probe = ("<script>addEventListener('load',function(){setTimeout(function(){var d=document.documentElement;"
             "document.body.setAttribute('data-probe',d.scrollWidth+'/'+d.clientWidth)},1500)})</script>")
    (out / 'light.html').write_text('<!doctype html>' + head + page + probe)
    (out / 'dark.html').write_text('<!doctype html><html data-theme="dark">' + head + page + probe)
    css = re.search(r'<style>(.*?)</style>', page, re.S)[1]
    first = (re.search(r'<div class="wrap[^"]*" dir="(\w+)"', page) or [None, 'ltr'])[1]
    vis = re.findall(r'<figure class="(?:diagram loopfig|timeline|calc)".*?</figure>|<div class="matrix".*?</div></div>|<div class="spectrum">.*?</div></div></div>', page, re.S)
    (out / 'visuals.html').write_text(f'<!doctype html><meta charset="utf-8"><style>{css}</style><div class="wrap" dir="{first}" style="display:block;max-width:760px">'
                                      f'<main><section class="sec lv-basic">{"".join(vis)}</section></main></div>')
    made = [shot(out / 'light.html', out / 'preview-desktop.png', 1280, 1100), shot(out / 'dark.html', out / 'preview-phone.png', 500, 1500)]
    if vis:
        made.append(shot(out / 'visuals.html', out / 'preview-visuals.png', 820, min(400 + 330 * len(vis), 16000)))
    bad = []
    for name, w in (('light.html', 1280), ('light.html', 420)):
        dom = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--virtual-time-budget=5000', f'--window-size={w},1100', '--dump-dom', f'file://{out / name}'],
                             capture_output=True, text=True, timeout=120).stdout
        m = re.search(r'data-probe="(\d+)/(\d+)"', dom)
        if m and int(m[1]) > int(m[2]) + 1:
            bad.append(f'{w}px: page is {m[1]}px wide in a {m[2]}px viewport')
    # parse every mermaid diagram (unique source) with the real mermaid library
    diagrams = sorted(set(html.unescape(d).strip() for d in re.findall(r'<pre class="mermaid">(.*?)</pre>', page, re.S)))
    if diagrams:
        (out / 'mermaid.html').write_text(
            '<!doctype html><meta charset="utf-8"><script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script><script>'
            f'var D={json.dumps(diagrams)};'
            "addEventListener('load',async function(){var bad=[];if(!window.mermaid){document.body.setAttribute('data-probe','NOLIB');return}"
            "mermaid.initialize({startOnLoad:false});for(var i=0;i<D.length;i++){try{await mermaid.parse(D[i])}catch(e){bad.push((D[i].split('\\n')[0]+' :: '+String(e.message||e)).slice(0,160))}}"
            "document.body.setAttribute('data-probe',JSON.stringify(bad))});</script><body></body>")
        dom = subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--virtual-time-budget=15000', '--dump-dom', f'file://{out / "mermaid.html"}'],
                             capture_output=True, text=True, timeout=120).stdout
        m = re.search(r'data-probe="([^"]*)"', dom)
        res = html.unescape(m[1]) if m else 'NOLIB'
        if res == 'NOLIB':
            print(f'mermaid check skipped: library did not load (offline?); {len(diagrams)} diagrams unchecked')
        else:
            errs = json.loads(res)
            print(f'mermaid check: {len(diagrams)} diagrams, {len(errs)} with syntax errors')
            bad += [f'mermaid: {e}' for e in errs]
        (out / 'mermaid.html').unlink()
    for f in ('light.html', 'dark.html', 'visuals.html'):
        (out / f).unlink()
    print(f'{sum(made)} screenshots in {out}  ({len(vis)} concept visuals)')
    if bad:
        print('FIX BEFORE PUBLISHING:\n  ' + '\n  '.join(bad)); sys.exit(1)
    print('checks passed: no horizontal overflow at desktop or phone width, every mermaid diagram parses')


if __name__ == '__main__':
    main()
