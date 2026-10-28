"""MkDocs hooks for the P501 documentation site.

The site is built from the markdown that lives next to the code (tools/docs_stage.py copies it into build/docs_src), so the pages keep working on GitHub too. Two things have to be fixed up at build time:
  1. a relative link to a file that is not a page of the site (a .py, .v, .tcl, .grc, a folder, ...) becomes a link to the file on GitHub;
  2. docs/overlays.md shows the overlay table of README.md (one source): the marker <!-- README:overlays --> is replaced by that section, with its links moved one folder down.
"""
import os
import re

REPO = "https://github.com/fllay/p501_fft_example"
BRANCH = "main"
PAGE_SUFFIX = {".md"}
MEDIA_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".pdf"}
LINK = re.compile(r"(\]\()([^)\s]+)((?:\s+\"[^\"]*\")?\))")


def _is_external(t):
    return t.startswith(("http://", "https://", "mailto:", "#", "/", "data:")) or "://" in t


def on_page_markdown(markdown, page, config, files):
    docs_dir = os.path.dirname(config["config_file_path"])      # the repository: where the files that are not pages live
    src_uri = page.file.src_uri

    if src_uri == "docs/overlays.md" and "<!-- README:overlays -->" in markdown:
        readme = open(os.path.join(docs_dir, "README.md"), encoding="utf-8").read()
        a = readme.index("## What is in this repository")
        b = readme.index("## Quick start")
        section = readme[a:b].split("\n", 1)[1]
        section = LINK.sub(lambda m: m.group(1) + (m.group(2) if _is_external(m.group(2)) else "../" + m.group(2)) + m.group(3), section)
        markdown = markdown.replace("<!-- README:overlays -->", section)

    base = os.path.dirname(src_uri)

    def fix(m):
        target = m.group(2)
        if _is_external(target):
            return m.group(0)
        path, _, frag = target.partition("#")
        if not path:
            return m.group(0)
        rel = os.path.normpath(os.path.join(base, path)).replace(os.sep, "/")
        suffix = os.path.splitext(rel)[1].lower()
        if suffix in MEDIA_SUFFIX and files.get_file_from_path(rel) is not None:
            return m.group(0)
        if suffix in PAGE_SUFFIX and files.get_file_from_path(rel) is not None:
            return m.group(0)
        full = os.path.join(docs_dir, rel)
        if os.path.isdir(full):
            url = f"{REPO}/tree/{BRANCH}/{rel}"
        elif os.path.isfile(full):
            url = f"{REPO}/blob/{BRANCH}/{rel}"
        else:
            return m.group(0)                       # a broken link: leave it, mkdocs reports it
        return m.group(1) + url + ("#" + frag if frag else "") + m.group(3)

    return LINK.sub(fix, markdown)
