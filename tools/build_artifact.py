"""Turn the generated docs/ pages into one clickable page plus deal fragments, for a
claude.ai Artifact (or any single-page host). Read-only on docs/.

  python tools/build_artifact.py docs out_dir "Snapshot note"

out_dir/app.html      the page (no <html>/<head>/<body>: the host adds them)
out_dir/p/<id>.html   one fragment per deal, loaded when you tap it
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rvdeals.pages import PREFS_JS  # noqa: E402

ID = re.compile(r"^[A-Za-z0-9-]+$")

APP_JS = r"""
function pick(btn){var g=btn.closest('[role=tablist]');g.querySelectorAll('[role=tab]').forEach(function(t){
var on=t===btn;t.setAttribute('aria-selected',on);t.tabIndex=on?0:-1;var p=document.getElementById(t.getAttribute('aria-controls'));if(p)p.hidden=!on;});
try{if(g.dataset.remember)localStorage.setItem('rvdh-'+g.dataset.remember,btn.dataset.key);}catch(e){}}
function initTabs(root){root.querySelectorAll('[role=tablist]').forEach(function(g){var tabs=[].slice.call(g.querySelectorAll('[role=tab]'));
tabs.forEach(function(t,i){t.addEventListener('click',function(){pick(t);});t.addEventListener('keydown',function(e){
var d=e.key==='ArrowRight'?1:e.key==='ArrowLeft'?-1:0;if(d){var n=tabs[(i+d+tabs.length)%tabs.length];n.focus();pick(n);}});});
var want=null;try{if(g.dataset.remember)want=localStorage.getItem('rvdh-'+g.dataset.remember);}catch(e){}
pick(tabs.filter(function(t){return t.dataset.key===want;})[0]||tabs.filter(function(t){return t.dataset.key===g.dataset.default;})[0]||tabs[0]);});
root.querySelectorAll('[data-goto]').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();
var b=root.querySelector('[role=tab][data-key="'+a.dataset.goto+'"]');if(b){pick(b);b.closest('.tabs').scrollIntoView({behavior:'smooth'});}});});}
var list=document.getElementById('list-view'),view=document.getElementById('deal-view'),cache={};
function route(){var h=location.hash.slice(1);
if(h.indexOf('d-')===0){var id=h.slice(2);list.hidden=true;view.hidden=false;
var show=function(html){view.innerHTML=html;initTabs(view);rvApply(view);window.scrollTo(0,0);var t=view.querySelector('h1');document.title=(t?t.textContent+' | ':'')+'RV Deal Hunter';};
if(cache[id]){show(cache[id]);return;}view.innerHTML='<p class="small" style="padding:40px 0">Loading the deal...</p>';
fetch('p/'+id+'.html').then(function(r){if(!r.ok)throw 0;return r.text();}).then(function(x){cache[id]=x;show(x);})
.catch(function(){view.innerHTML='<div class="card empty">This deal could not be loaded. <a href="#">Back to all deals</a></div>';});}
else{view.hidden=true;list.hidden=false;document.title='RV Deal Hunter';}}
document.addEventListener('click',function(e){var a=e.target.closest('a[href="#"]');if(a){e.preventDefault();
if(location.hash){location.hash='';}route();window.scrollTo(0,0);}});
document.documentElement.classList.add('js');initTabs(list);window.addEventListener('hashchange',route);route();
"""


def _main(html: str) -> str:
    m = re.search(r"<main>(.*)</main>", html, re.S)
    if not m:
        raise ValueError("no <main> in page")
    return m.group(1)


def build(docs: Path, out: Path, note: str) -> int:
    index = (docs / "index.html").read_text()
    style = re.search(r"<style>(.*?)</style>", index, re.S).group(1)
    body = _main(index)
    body = re.sub(r'href="p/([A-Za-z0-9-]+)\.html"', r'href="#d-\1"', body)
    body = body.replace('data-hash="1"', 'data-hash="" data-remember="list"')
    # The settings panel comes from the deals list itself; put this snapshot's note in "About this page".
    body, n = re.subn(r"<!--about-->.*?<!--/about-->", lambda m_: note, body, count=1, flags=re.S)
    if not n or 'id="gear"' not in body:
        raise ValueError("settings panel not found on the deals list")
    (out / "p").mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted((docs / "p").glob("*.html")):
        if not ID.match(f.stem):
            continue
        frag = _main(f.read_text())
        frag = frag.replace('href="../"', 'href="#"').replace('data-hash="1"', 'data-hash=""')
        (out / "p" / f.name).write_text(frag)
        n += 1
    extra_css = ""
    page = (f'<title>RV Deal Hunter</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            f'<meta name="robots" content="noindex">\n<style>{style}{extra_css}</style>\n'
            f'<main><div id="list-view">{body}</div><div id="deal-view" hidden></div></main>\n'
            f'<script>{APP_JS}{PREFS_JS}</script>\n')
    (out / "app.html").write_text(page)
    return n


if __name__ == "__main__":
    docs, out, note = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    print(f"{build(docs, out, note)} deal pages")
