#!/usr/bin/env python3
"""Builds a single self-contained HTML page (images embedded, code highlighted, table of contents) from tutorial/TUTORIAL_QPSK.md.

    python3 build_page.py out.html          (needs the `markdown` and `pygments` packages, e.g. the radioconda environment)
"""
import base64, os, re, sys
import markdown
from pygments.formatters import HtmlFormatter  # noqa: F401  (codehilite uses pygments; imported so a missing package fails early)

HERE = os.path.dirname(os.path.abspath(__file__))
TUT = os.path.normpath(os.path.join(HERE, "..", ".."))
out_path = sys.argv[1] if len(sys.argv) > 1 else "tutorial_qpsk.html"

md = open(os.path.join(TUT, "TUTORIAL_QPSK.md")).read()
md = re.sub(r"^\*This file is generated:.*?\*\n", "", md, count=1, flags=re.S | re.M)          # a note about the repository, not for the reader of the page
body = markdown.markdown(md, extensions=["fenced_code", "tables", "toc", "sane_lists", "codehilite"],
                         extension_configs={"codehilite": {"guess_lang": False, "css_class": "codehilite"}, "toc": {"permalink": False}})


def embed(m):
    path = os.path.join(TUT, m.group(1))
    data = base64.b64encode(open(path, "rb").read()).decode()
    return 'src="data:image/png;base64,%s"' % data


body = re.sub(r'src="(img/[^"]+\.png)"', embed, body)
body = body.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
body = re.sub(r"<img ", '<img loading="lazy" ', body)

# table of contents from the h1 (parts) and h2 (sections)
heads = re.findall(r'<h([12]) id="([^"]+)">(.*?)</h\1>', body, flags=re.S)
toc, depth_open = [], False
for lvl, hid, txt in heads:
    txt = re.sub(r"<[^>]+>", "", txt)
    if lvl == "1":
        if depth_open: toc.append("</ul>")
        toc.append('<a class="part" href="#%s">%s</a><ul>' % (hid, txt)); depth_open = True
    else:
        toc.append('<li><a href="#%s">%s</a></li>' % (hid, txt))
if depth_open: toc.append("</ul>")
toc_html = "\n".join(toc)

CSS = r"""
:root {
  /* layout: a sticky contents column beside one reading column; code and tables scroll inside their own boxes */
  --bg: #f6f8fa; --panel: #ffffff; --fg: #17222c; --muted: #5a6b7a; --line: #d5dde5;
  --accent: #0a6a86; --accent-soft: #dcecf2; --code-bg: #eef2f6; --code-fg: #1b2a36;
  --c-com: #66788a; --c-kw: #0b5f8a; --c-str: #9a4a12; --c-num: #6b3fa0; --c-fn: #1a7a52;
  --font-body: "Source Sans 3", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0f1720; --panel: #16212c; --fg: #dde6ee; --muted: #93a4b4; --line: #2a3947;
    --accent: #5cc2de; --accent-soft: #173543; --code-bg: #101b25; --code-fg: #d3dfe9;
    --c-com: #7f93a6; --c-kw: #6fc3ef; --c-str: #e3a36d; --c-num: #b99be3; --c-fn: #6fd2a2; color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #0f1720; --panel: #16212c; --fg: #dde6ee; --muted: #93a4b4; --line: #2a3947;
  --accent: #5cc2de; --accent-soft: #173543; --code-bg: #101b25; --code-fg: #d3dfe9;
  --c-com: #7f93a6; --c-kw: #6fc3ef; --c-str: #e3a36d; --c-num: #b99be3; --c-fn: #6fd2a2; color-scheme: dark;
}
html { scroll-behavior: smooth; scroll-padding-top: 1rem; }
body { background: var(--bg); color: var(--fg); font-family: var(--font-body); font-size: 17px; line-height: 1.6; }
* { box-sizing: border-box; }
.shell { display: grid; grid-template-columns: minmax(0, 1fr); gap: 2rem; max-width: 78rem; margin: 0 auto; padding-inline: 16px; padding-block: 1.5rem 4rem; }
@media (min-width: 62rem) { .shell { grid-template-columns: 17rem minmax(0, 1fr); } }
nav.side { display: none; }
@media (min-width: 62rem) {
  nav.side { display: block; position: sticky; top: env(safe-area-inset-top, 0px); align-self: start; max-height: 100vh; overflow-y: auto; padding-block: 0.5rem 2rem; font-size: 0.86rem; }
  details.toc-m { display: none; }
}
nav.side a, details.toc-m a { color: var(--muted); text-decoration: none; }
nav.side a:hover, details.toc-m a:hover { color: var(--accent); }
nav.side a.part, details.toc-m a.part { display: block; margin-top: 1.1rem; font-weight: 700; color: var(--fg); letter-spacing: 0.01em; }
nav.side ul, details.toc-m ul { list-style: none; margin: 0.25rem 0 0; padding: 0 0 0 0.7rem; border-left: 1px solid var(--line); }
nav.side li, details.toc-m li { margin: 0.18rem 0; line-height: 1.35; }
nav.side a.on { color: var(--accent); font-weight: 600; }
.toc-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.12em; color: var(--muted); margin-bottom: 0.2rem; }
details.toc-m { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 0.6rem 0.9rem; font-size: 0.92rem; }
details.toc-m summary { cursor: pointer; font-weight: 600; }
article { min-width: 0; max-width: 54rem; }
article > h1:first-child { font-size: 2.1rem; line-height: 1.15; margin: 0.2rem 0 1rem; text-wrap: balance; letter-spacing: -0.01em; }
article h1 { font-size: 1.65rem; line-height: 1.2; margin: 3.2rem 0 1rem; padding-top: 1.4rem; border-top: 2px solid var(--accent); text-wrap: balance; }
article > h1:first-child { border-top: 0; padding-top: 0; }
article h2 { font-size: 1.28rem; line-height: 1.25; margin: 2.3rem 0 0.6rem; text-wrap: balance; }
article h3 { font-size: 1.05rem; margin: 1.6rem 0 0.4rem; }
article p, article li { max-width: 70ch; }
article p { margin: 0.7rem 0; }
article ul, article ol { padding-left: 1.4rem; }
article li { margin: 0.25rem 0; }
article a { color: var(--accent); }
article hr { border: 0; border-top: 1px solid var(--line); margin: 2rem 0; }
code { font-family: var(--font-mono); font-size: 0.86em; background: var(--code-bg); color: var(--code-fg); padding: 0.08em 0.32em; border-radius: 3px; overflow-wrap: anywhere; }
.codehilite { background: var(--code-bg); border: 1px solid var(--line); border-radius: 6px; margin: 1rem 0 0.15rem; overflow-x: auto; }
.codehilite pre { margin: 0; padding: 0.85rem 1rem; font-size: 0.8rem; line-height: 1.5; }
.codehilite code { background: none; padding: 0; font-size: inherit; overflow-wrap: normal; white-space: pre; color: var(--code-fg); }
.codehilite + p { margin: 0 0 1.1rem; font-size: 0.78rem; color: var(--muted); }
.codehilite + p code { font-size: 0.95em; background: none; padding: 0; }
.tw { overflow-x: auto; margin: 1rem 0; border: 1px solid var(--line); border-radius: 6px; background: var(--panel); }
table { border-collapse: collapse; width: 100%; font-size: 0.88rem; line-height: 1.45; }
th, td { padding: 0.45rem 0.7rem; text-align: left; vertical-align: top; border-bottom: 1px solid var(--line); }
th { background: var(--accent-soft); font-weight: 600; white-space: nowrap; }
tr:last-child td { border-bottom: 0; }
td code, th code { font-size: 0.82em; }
td { min-width: 6rem; }
img { display: block; max-width: 100%; height: auto; margin: 1.1rem auto; border: 1px solid var(--line); border-radius: 6px; background: #fff; }
em { font-style: italic; }
.codehilite .c, .codehilite .c1, .codehilite .cm, .codehilite .cs, .codehilite .ch { color: var(--c-com); font-style: italic; }
.codehilite .k, .codehilite .kd, .codehilite .kn, .codehilite .kr, .codehilite .kt, .codehilite .kc, .codehilite .kp, .codehilite .ow { color: var(--c-kw); font-weight: 600; }
.codehilite .s, .codehilite .s1, .codehilite .s2, .codehilite .sb, .codehilite .sa, .codehilite .sc, .codehilite .se, .codehilite .si { color: var(--c-str); }
.codehilite .m, .codehilite .mi, .codehilite .mf, .codehilite .mh, .codehilite .mb, .codehilite .mo, .codehilite .il { color: var(--c-num); }
.codehilite .nf, .codehilite .nb, .codehilite .nc, .codehilite .fm, .codehilite .nn, .codehilite .nd { color: var(--c-fn); }
.codehilite .cp { color: var(--c-kw); }
@media (max-width: 40rem) { body { font-size: 16px; } article > h1:first-child { font-size: 1.7rem; } article h1 { font-size: 1.4rem; } }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
"""

JS = r"""
(function () {
  var links = document.querySelectorAll('nav.side a');
  var map = {};
  links.forEach(function (a) { map[a.getAttribute('href').slice(1)] = a; });
  var heads = Array.prototype.slice.call(document.querySelectorAll('article h1[id], article h2[id]'));
  if (!('IntersectionObserver' in window)) return;
  var cur = null;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting && map[e.target.id]) {
        if (cur) cur.classList.remove('on');
        cur = map[e.target.id]; cur.classList.add('on');
      }
    });
  }, { rootMargin: '0px 0px -75% 0px' });
  heads.forEach(function (h) { io.observe(h); });
})();
"""

page = """<title>P501 QPSK Modem Tutorial</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&display=swap">
<style>%s</style>
<div class="shell">
<nav class="side" aria-label="Contents"><div class="toc-label">Contents</div>
%s
</nav>
<div>
<details class="toc-m"><summary>Contents</summary>
%s
</details>
<article>
%s
</article>
</div>
</div>
<script>%s</script>
""" % (CSS, toc_html, toc_html, body, JS)
open(out_path, "w").write(page)
print("wrote", out_path, "%.0f KB" % (len(page) / 1024), "headings:", len(heads))
