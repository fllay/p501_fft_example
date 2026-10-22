#!/usr/bin/env python3
"""Builds tutorial/TUTORIAL_QPSK.md from TUTORIAL_QPSK.src.md: every line of the form

    @@ path/from/repo/root  first_line  last_line  [optional note]

is replaced by a fenced code block with exactly those lines of that file (so the code in the text is always the code of the repository),
and a caption line with the file name and the line range. `@@ path` with no range inserts the whole file.

    python3 build_doc.py            (run from anywhere)
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(HERE, "TUTORIAL_QPSK.src.md")
OUT = os.path.join(ROOT, "tutorial", "TUTORIAL_QPSK.md")
LANG = {".v": "verilog", ".py": "python", ".tcl": "tcl", ".xdc": "tcl", ".sh": "bash"}


def snippet(spec):
    parts = spec.split(None, 3)
    path = parts[0]; full = os.path.join(ROOT, path)
    lines = open(full).read().split("\n")
    if len(parts) >= 3:
        a, b = int(parts[1]), int(parts[2]); note = parts[3] if len(parts) > 3 else ""
        if not (1 <= a <= b <= len(lines)): sys.exit("bad range %s" % spec)
        body = lines[a - 1:b]; cap = "`%s`, lines %d-%d" % (path, a, b)
    else:
        a, note = 1, ""; body = lines[:-1] if lines[-1] == "" else lines; cap = "`%s`" % path
    # strip a common indent so the excerpt is not pushed to the right
    ind = min((len(l) - len(l.lstrip()) for l in body if l.strip()), default=0)
    body = [l[ind:] for l in body]
    lang = LANG.get(os.path.splitext(path)[1], "")
    return "```%s\n%s\n```\n*%s%s*\n" % (lang, "\n".join(body), cap, (" - " + note) if note else "")


out = []
for line in open(SRC).read().split("\n"):
    m = re.match(r"^@@\s+(.*)$", line)
    out.append(snippet(m.group(1)) if m else line.replace("](../../img/", "](img/"))     # the source sits two folders deeper than the built tutorial: its figures are ../../img/, the built file's img/
open(OUT, "w").write("\n".join(out))
print("wrote", OUT, "(%d lines)" % len("\n".join(out).split("\n")))
