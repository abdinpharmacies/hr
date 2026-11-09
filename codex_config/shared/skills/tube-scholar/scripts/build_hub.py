#!/usr/bin/env python3
"""Build one hub page for a playlist or course series that links every video's study guide.

Usage: build_hub.py <hub.html> "<hub title>" <guide-dir> [<guide-dir> ...]

Each guide-dir needs guide.json with "artifact_url" (saved after publishing that guide) and
meta/ from fetch_meta.py. The hub shows every video in order with its thumbnail, duration and
guide size, a "watched/studied" tick per video kept in this browser, overall progress, and an
Arabic/English switch. Open the hub locally or publish to an authorized static host.
"""
import base64, html, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_guide import bidi, RTL  # noqa: E402  (same Latin-in-Arabic isolation as the guides)

ASSETS = Path(__file__).resolve().parent.parent / 'assets'
T = {
 'ar': dict(dir='rtl', kicker='STUDY PATH · مسار مذاكرة', sub='كل فيديو في الكورس ليه دليل كامل: خلاصة في 5 دقايق، وشرح لكل جزء، وأسئلة سيناريو، و Flashcards.',
            open='افتح الدليل', done='خلصته', todo='علّم إنه خلص', prog='خلصت {n} من {t}', cards='كارت', secs='قسم', missing='الدليل لسه ماتنشرش'),
 'en': dict(dir='ltr', kicker='STUDY PATH', sub='Every video in the course has a full guide: a 5-minute summary, an explanation of each part, scenario questions and flashcards.',
            open='Open the guide', done='Done', todo='Mark as done', prog='{n} of {t} done', cards='cards', secs='sections', missing='Guide not published yet'),
}


def uri(p):
    return 'data:image/jpeg;base64,' + base64.b64encode(p.read_bytes()).decode() if p.exists() else ''


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    out, title, dirs = Path(sys.argv[1]), sys.argv[2], [Path(d).expanduser() for d in sys.argv[3:]]
    items = []
    for d in dirs:
        g = json.loads((d / 'guide.json').read_text()); v = json.loads((d / 'meta/video.json').read_text())
        n_cards = sum(1 for l in (d / f'cards.{g["langs"][0]}.txt').read_text().splitlines() if l.strip() and not l.startswith('#'))
        n_secs = sum(1 for l in (d / f'guide.{g["langs"][0]}.md').read_text().splitlines() if l.startswith('## ') and l[3:4].isdigit())
        items.append(dict(id=v['id'], title=v['title'], dur=v.get('duration_string', ''), url=g.get('artifact_url', ''), h1=g['h1'], em=g.get('h1_em', {}),
                          thumb=uri(d / 'meta/thumb.jpg'), cards=n_cards, secs=n_secs, langs=g['langs']))
    langs = [l for l in ('ar', 'en') if all(l in it['langs'] for it in items)] or ['en']
    e = html.escape
    wraps = []
    for ix, lang in enumerate(langs):
        t = T[lang]; iso = bidi if lang in RTL else (lambda h: h)
        cards = ''.join(
            f'<li class="hub-item" data-id="{it["id"]}"><a class="hub-thumb" href="{e(it["url"]) or "#"}" target="_blank" rel="noopener"><img src="{it["thumb"]}" alt=""><span class="dur">{e(it["dur"])}</span></a>'
            f'<div class="hub-body"><span class="hub-n">{i + 1:02d}</span><b>{iso(e(it["h1"].get(lang, it["title"])))} <em>{iso(e(it["em"].get(lang, "")))}</em></b>'
            f'<span class="hub-orig" dir="ltr">{e(it["title"])}</span><span class="hub-meta">{it["secs"]} {t["secs"]} · {it["cards"]} {t["cards"]}</span>'
            f'<div class="hub-acts">' + (f'<a class="lnk yt" href="{e(it["url"])}" target="_blank" rel="noopener">{t["open"]}</a>' if it['url'] else f'<span class="hub-miss">{t["missing"]}</span>')
            + f'<button class="done" type="button" data-id="{it["id"]}" aria-pressed="false"><span class="ck" aria-hidden="true"></span>{t["todo"]}</button></div></div></li>'
            for i, it in enumerate(items))
        wraps.append(f'<div class="wrap hub" dir="{t["dir"]}" lang="{lang}" data-lang="{lang}"{" hidden" if ix else ""}><header class="top"><div class="eyebrow"><span class="pill">{t["kicker"]}</span></div>'
                     f'<h1>{e(title)}</h1><p class="sub">{iso(t["sub"])}</p><div class="rail-prog hub-prog"><div class="rp-top"><b class="hub-count"></b></div><div class="bar"><i></i></div></div></header>'
                     f'<main><ol class="hub-list">{cards}</ol></main></div>')
    sw = ('<div class="langsw" role="group" aria-label="Language">' + ''.join(f'<button type="button" data-l="{l}" aria-pressed="{str(i == 0).lower()}">{"عربي" if l == "ar" else "English"}</button>' for i, l in enumerate(langs)) + '</div>') if len(langs) > 1 else ''
    css = (ASSETS / 'guide.css').read_text() + '''
.wrap.hub{display:block;max-width:980px}
.hub h1{margin-top:8px}
.hub-prog{max-width:420px;margin-top:6px}
.hub-list{list-style:none;padding:0;margin:24px 0;display:flex;flex-direction:column;gap:14px}
.hub-item{max-width:none!important;margin:0!important;display:grid;grid-template-columns:minmax(0,280px) minmax(0,1fr);gap:18px;align-items:start;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:14px;box-shadow:var(--shadow)}
.hub-item.ok{border-color:var(--accent)}
.hub-thumb{position:relative;display:block;border-radius:10px;overflow:hidden;aspect-ratio:16/9}
.hub-thumb img{width:100%;height:100%;object-fit:cover;display:block}
.hub-body{display:flex;flex-direction:column;gap:4px;min-width:0}
.hub-n{font-family:var(--mono);font-size:12px;color:var(--accent);font-weight:600}
.hub-body b{font-family:var(--display);font-size:18px;line-height:1.5}
.hub-body em{font-style:normal;color:var(--accent)}
.hub-orig{font-family:var(--latin);font-size:13px;color:var(--muted)}
.hub-meta{font-size:12.5px;color:var(--muted)}
.hub-acts{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;align-items:center}
.hub-miss{font-size:13px;color:var(--note)}
@media (max-width:640px){.hub-item{grid-template-columns:minmax(0,1fr)}}
'''
    js = '''(function(){
  var KEY='ythub-'+%s, st={done:[],lang:'%s'};
  try{var o=JSON.parse(localStorage.getItem(KEY)||'{}'); st.done=o.done||[]; if(o.lang) st.lang=o.lang;}catch(e){}
  function save(){try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}}
  var L={ar:{done:'%s',todo:'%s',prog:'%s'},en:{done:'%s',todo:'%s',prog:'%s'}};
  function paint(){
    document.querySelectorAll('.wrap[data-lang]').forEach(function(w){
      var l=L[w.dataset.lang], n=0, items=w.querySelectorAll('.hub-item');
      items.forEach(function(it){var on=st.done.indexOf(it.dataset.id)>-1; if(on)n++; it.classList.toggle('ok',on);
        var b=it.querySelector('.done'); b.setAttribute('aria-pressed',String(on)); b.lastChild.textContent=on?l.done:l.todo;});
      w.querySelector('.hub-count').textContent=l.prog.replace('{n}',n).replace('{t}',items.length);
      w.querySelector('.hub-prog .bar i').style.transform='scaleX('+(items.length?n/items.length:0)+')';
    });
  }
  document.querySelectorAll('.done').forEach(function(b){b.addEventListener('click',function(){var k=st.done.indexOf(b.dataset.id); if(k>-1)st.done.splice(k,1); else st.done.push(b.dataset.id); save(); paint();});});
  function setLang(l){st.lang=l; save(); document.querySelectorAll('.wrap[data-lang]').forEach(function(w){w.hidden=w.dataset.lang!==l});
    document.documentElement.lang=l; var w=document.querySelector('.wrap[data-lang="'+l+'"]'); if(w) document.documentElement.dir=w.getAttribute('dir');
    document.querySelectorAll('.langsw button').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.l===l))});}
  document.querySelectorAll('.langsw button').forEach(function(b){b.addEventListener('click',function(){setLang(b.dataset.l)})});
  setLang(document.querySelector('.wrap[data-lang="'+st.lang+'"]')?st.lang:'%s'); paint();
})();''' % (json.dumps(items[0]['id']), langs[0], T['ar']['done'], T['ar']['todo'], T['ar']['prog'], T['en']['done'], T['en']['todo'], T['en']['prog'], langs[0])
    out.write_text(f'<title>{e(title)}</title>\n<meta name="viewport" content="width=device-width,initial-scale=1">\n'
                   '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&family=Noto+Kufi+Arabic:wght@500;700;800&display=swap">\n'
                   f'<style>{css}</style>\n{sw}\n' + '\n'.join(wraps) + f'\n<script>{js}</script>\n')
    print(f'{out}  {len(items)} videos  langs={",".join(langs)}  missing urls: {sum(1 for it in items if not it["url"])}')


if __name__ == '__main__':
    main()
