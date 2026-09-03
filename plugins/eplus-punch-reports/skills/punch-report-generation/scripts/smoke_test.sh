#!/usr/bin/env bash
#
# smoke_test.sh -- prove every documented command actually exists and parses.
#
# This exists because the previous generation of this pipeline documented three
# features its shipped code did not have: a TOC dot-leader alignment that was
# really padded dots, an "--items-from" interface on a script that accepted no
# arguments at all, and a review_sheet.py that was simply absent. All three
# would have been caught here in under a second.
#
# Run from the skill's scripts/ directory, or from a project's _pipeline dir:
#     bash scripts/smoke_test.sh
#
set -u
cd "$(dirname "$0")"

# Force UTF-8 for every Python step. Without this, Windows Python reads the
# model-written UTF-8 JSON as the ANSI code page: an em dash becomes mojibake
# that the dash check no longer catches, and it renders into the report.
export PYTHONUTF8=1

# The pipeline normally runs on the Linux side, where the interpreter is
# python3; a Windows host usually only has `python`. Resolve rather than assume,
# so a wrong interpreter name cannot masquerade as a missing dependency.
# Probe by RUNNING the candidate, not with `command -v`: on Windows, a
# Microsoft Store alias stub named python3 sits on PATH and fails when invoked,
# so an existence check picks an interpreter that cannot run anything.
PY=""
for cand in python3 python; do
    if "$cand" -c 'import sys; sys.exit(0)' >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
    echo "ERROR: no working python interpreter on PATH (tried python3, then python)." >&2
    exit 1
fi

fail=0
ok()   { printf '  [PASS] %s\n' "$1"; }
bad()  { printf '  [FAIL] %s\n' "$1"; fail=$((fail+1)); }

echo "smoke test: $(pwd)"
echo

# Every python entry point must answer --help without importing its heavy deps
# failing the run. A missing dep is reported separately from a broken interface.
for s in consolidate.py normalize_photos.py extract_sheet_clips.py \
         build_master.py review_sheet.py verify_report.py read_comments.py \
         package.py fix_bookmark_ids.py render_preview.py \
         import_reviewed_docx.py; do
    if [ ! -f "$s" ]; then bad "$s is missing"; continue; fi
    out=$("$PY" "$s" --help 2>&1)
    case "$?:$out" in
        0:*)                   ok "$s --help" ;;
        *:*ModuleNotFoundError*) bad "$s: missing dependency -> $(printf '%s' "$out" | tail -1)" ;;
        *)                     bad "$s --help exited nonzero -> $(printf '%s' "$out" | tail -1)" ;;
    esac
done

# The renderer has no --help; require it to parse and to refuse a missing build.
if [ ! -f gen_report.js ]; then
    bad "gen_report.js is missing"
elif node --check gen_report.js >/dev/null 2>&1; then
    ok "gen_report.js parses"
else
    bad "gen_report.js has a syntax error"
fi

[ -f run_pipeline.sh ] && bash -n run_pipeline.sh 2>/dev/null \
    && ok "run_pipeline.sh parses" || bad "run_pipeline.sh missing or unparseable"
[ -f install_deps.sh ] && bash -n install_deps.sh 2>/dev/null \
    && ok "install_deps.sh parses" || bad "install_deps.sh missing or unparseable"
[ -f requirements.txt ] && ok "requirements.txt present" || bad "requirements.txt missing"

# Behavioural checks on the pure-stdlib helpers, so a regression in the merge or
# protection logic is caught here and not on a live report.
"$PY" - <<'PYCHECK' 2>&1 && ok "build_master.py: merges block, origin protection, photo_mode" \
    || bad "build_master.py behavioural check failed"
import json, os, subprocess, sys, tempfile
d = tempfile.mkdtemp()
items = [
  {"number": 1, "photos": [{"uid": "a", "title": "20260101_100000_a", "captured": "20260101T100000", "path": "/p/a__20260101_100000_a.jpg"}],
   "sheet_name": "TO2-01A", "sheet_description": "Plan", "room": "", "status": "open"},
  {"number": 2, "photos": [{"uid": "b", "title": "20260101_090000_b", "captured": "20260101T090000", "path": "/p/b__20260101_090000_b.jpg"}],
   "sheet_name": "T02-01A", "sheet_description": "Plan", "room": "", "status": "open"},
  {"number": 3, "photos": [], "sheet_name": None, "sheet_description": None, "room": "", "status": "open"},
]
drafted = {"items": [
  {"number": 1, "title": "Alpha", "description": "Conduit stubbed up.", "corrective_action": "fix it",
   "origin": "photo_inferred", "confidence": "low"},
  {"number": 3, "title": "Gamma", "description": "Approved text, kept verbatim.",
   "corrective_action": "leave as is", "origin": "user_reviewed", "photo_mode": "none"},
], "merges": [{"into": 1, "from": 2}]}
json.dump(items, open(os.path.join(d, "items.json"), "w", encoding="utf-8"))
json.dump(drafted, open(os.path.join(d, "drafted.json"), "w", encoding="utf-8"))
out = os.path.join(d, "master.json")
r = subprocess.run([sys.executable, "build_master.py", "--items", os.path.join(d, "items.json"),
                    "--drafted", os.path.join(d, "drafted.json"), "-o", out],
                   capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
m = {x["plangrid_ref"]: x for x in json.load(open(out, encoding="utf-8"))}
assert set(m) == {"#1", "#3"}, list(m)                      # pin 2 absorbed and omitted
assert m["#1"]["photo_paths"] == ["b.jpg", "a.jpg"], m["#1"]["photo_paths"]  # chronological
assert m["#1"]["corrective_action"] == "Fix it"              # capitalised when not protected
assert m["#3"]["corrective_action"] == "leave as is"         # protected: untouched
assert m["#3"]["photo_mode"] == "none"
assert m["#1"]["sheet_name"] == "T02-01A"                    # OCR letter-O repaired
assert "field_note_original" in m["#1"]
# a protected entry that sanitize would alter must fail the build
drafted["items"][1]["description"] = "bad \u2014 dash"
json.dump(drafted, open(os.path.join(d, "drafted.json"), "w", encoding="utf-8"))
r = subprocess.run([sys.executable, "build_master.py", "--items", os.path.join(d, "items.json"),
                    "--drafted", os.path.join(d, "drafted.json"), "-o", out],
                   capture_output=True, text=True)
assert r.returncode != 0 and "not sanitize-clean" in (r.stdout + r.stderr)
PYCHECK

"$PY" - <<'PYCHECK' 2>&1 && ok "consolidate.py: multi-delta layering, oldest first" \
    || bad "consolidate.py behavioural check failed"
import json, os, subprocess, sys, tempfile
d = tempfile.mkdtemp()
def layer(name, tasks):
    p = os.path.join(d, name) if name else d
    os.makedirs(os.path.join(p, "photos"), exist_ok=True)
    json.dump(tasks, open(os.path.join(p, "tasks.json"), "w", encoding="utf-8"))
    json.dump([], open(os.path.join(p, "sheets.json"), "w", encoding="utf-8"))
t = lambda n, uid, desc: {"number": n, "uid": uid, "title": "", "description": desc, "status": "open"}
layer("", [t(1, "u1", "base one")])
layer("delta_2026-08-14_to_2026-08-24", [t(2, "u2", "first delta"), t(1, "u1", "one revised")])
layer("delta_2026-08-25_to_2026-08-26", [t(3, "u3", "second delta")])
out = os.path.join(d, "items.json")
r = subprocess.run([sys.executable, "consolidate.py", d, "-o", out], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
items = {i["number"]: i for i in json.load(open(out, encoding="utf-8"))}
assert set(items) == {1, 2, 3}, list(items)                  # nothing from an older delta lost
assert items[1]["description"] == "one revised"              # later layer wins by uid
assert "delta_2026-08-14" in r.stdout and "delta_2026-08-25" in r.stdout
PYCHECK

"$PY" - <<'PYCHECK' 2>&1 && ok "fix_bookmark_ids.py: renumbers duplicate ids, canonical PAGEREF" \
    || bad "fix_bookmark_ids.py behavioural check failed"
import os, re, subprocess, sys, tempfile, zipfile
d = tempfile.mkdtemp()
p = os.path.join(d, "t.docx")
doc = ('<w:document><w:body>'
       '<w:p><w:bookmarkStart w:id="1" w:name="punchitem1"/><w:bookmarkEnd w:id="1"/></w:p>'
       '<w:p><w:bookmarkStart w:id="1" w:name="punchitem2"/><w:bookmarkEnd w:id="1"/></w:p>'
       '<w:p><w:r><w:instrText xml:space="preserve">PAGEREF punchitem1</w:instrText></w:r></w:p>'
       '</w:body></w:document>')
with zipfile.ZipFile(p, "w") as z:
    z.writestr("[Content_Types].xml", "<Types/>")
    z.writestr("word/document.xml", doc)
r = subprocess.run([sys.executable, "fix_bookmark_ids.py", p], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
x = zipfile.ZipFile(p).read("word/document.xml").decode()
ids = re.findall(r'<w:bookmarkStart[^>]*w:id="(\d+)"', x)
assert ids == ["1", "2"], ids
assert ' PAGEREF punchitem1 \\h ' in x, x
assert zipfile.ZipFile(p).namelist()[0] == "[Content_Types].xml"
PYCHECK

# The wording-review preview markup ships with the skill, not the workspace, so
# only assert it when running from a skill checkout.
if [ -d ../templates ]; then
    [ -f ../templates/item-preview.html ] && ok "templates/item-preview.html present" \
        || bad "templates/item-preview.html missing"
fi

# Deps the pipeline cannot run without.
"$PY" -c 'import pymupdf' 2>/dev/null && ok "pymupdf"  || bad "pymupdf not installed (bash scripts/install_deps.sh)"
"$PY" -c 'import PIL'     2>/dev/null && ok "pillow"   || bad "pillow not installed (bash scripts/install_deps.sh)"
"$PY" -c 'import openpyxl' 2>/dev/null && ok "openpyxl" || bad "openpyxl not installed (bash scripts/install_deps.sh)"
node -e 'require("docx")'   2>/dev/null && ok "docx"     || bad "docx not installed (bash scripts/install_deps.sh)"

echo
if [ "$fail" -gt 0 ]; then
    echo "$fail check(s) FAILED"
    exit 1
fi
echo "all checks passed"
