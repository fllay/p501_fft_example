#!/usr/bin/env python3
"""Stage the documentation for MkDocs: copies the markdown pages and the images of the repository, with the same folder layout, into build/docs_src (the docs_dir of mkdocs.yml).
The pages stay where they are (next to the code, readable on GitHub); MkDocs does not accept the repository root as its docs_dir, so it reads this copy.
    python3 tools/docs_stage.py && mkdocs build -d ../p501_site        (or: mkdocs serve)"""
import os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "docs_src")
PAGE_DIRS = ["tutorial", "docs"]                       # trees searched for pages and images
ROOT_PAGES = ["index.md"]
MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}
SKIP_DIRS = {"sim", "xsim.dir", "__pycache__", "ref", "doc", "steps", "dds_steps", ".git", "build"}     # tutorial/qpsk/doc is the source of a generated file, steps are Tcl
SKIP_FILES = {"HANDOFF.md"}


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    n_md = n_img = 0
    for name in ROOT_PAGES:
        os.makedirs(OUT, exist_ok=True)
        shutil.copy2(os.path.join(ROOT, name), os.path.join(OUT, name)); n_md += 1
    for top in PAGE_DIRS:
        for d, dirs, files in os.walk(os.path.join(ROOT, top)):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if f in SKIP_FILES or not (ext == ".md" or ext in MEDIA):
                    continue
                rel = os.path.relpath(os.path.join(d, f), ROOT)
                os.makedirs(os.path.dirname(os.path.join(OUT, rel)), exist_ok=True)
                shutil.copy2(os.path.join(d, f), os.path.join(OUT, rel))
                if ext == ".md": n_md += 1
                else: n_img += 1
    print("staged %d pages and %d images in %s" % (n_md, n_img, os.path.relpath(OUT, ROOT)))


if __name__ == "__main__":
    sys.exit(main())
