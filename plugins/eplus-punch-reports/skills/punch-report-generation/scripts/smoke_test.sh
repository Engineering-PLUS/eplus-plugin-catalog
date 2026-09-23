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

# The bash running this test, in a form the host python can exec (on a Windows
# dev box a bare "bash" from python resolves to WSL's). Used by the checks that
# run shell scripts from python.
export SMOKE_BASH="$(cygpath -w "$BASH" 2>/dev/null || echo "$BASH")"

echo "smoke test: $(pwd)"
echo

# Every python entry point must answer --help without importing its heavy deps
# failing the run. A missing dep is reported separately from a broken interface.
for s in consolidate.py normalize_photos.py extract_sheet_clips.py \
         build_master.py review_sheet.py verify_report.py read_comments.py \
         package.py fix_bookmark_ids.py render_preview.py \
         import_reviewed_docx.py fetch_photos.py adapt_mcp_pull.py \
         extract_pdf_photos.py export_pdf.py run_record.py staple_pdf.py \
         locate_inputs.py prefill_config.py finish_list.py update_report.py; do
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
[ -f init_workspace.sh ] && bash -n init_workspace.sh 2>/dev/null \
    && ok "init_workspace.sh parses" || bad "init_workspace.sh missing or unparseable"
[ -f requirements.txt ] && ok "requirements.txt present" || bad "requirements.txt missing"

# init_workspace.sh lays the workspace out the one way the pipeline reads it.
# Only testable from a skill checkout (the template sits beside scripts/).
if [ -d ../template/_pipeline ]; then
"$PY" - <<'PYCHECK' 2>&1 && ok "init_workspace.sh: stamps template at the root, refreshes scripts, keeps edits, checks layout" \
    || bad "init_workspace.sh behavioural check failed"
import os, subprocess, sys, tempfile, zipfile
bash = os.environ.get("SMOKE_BASH") or "bash"
d = tempfile.mkdtemp(); ws = os.path.join(d, "ws")
r = subprocess.run([bash, "init_workspace.sh", ws], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
for p in ("_pipeline/CLAUDE.md", "_pipeline/build/report.config.json", "_pipeline/build/assets/logos/ep_logo.jpg",
          "_pipeline/scripts/run_pipeline.sh", "_pipeline/scripts/init_workspace.sh", "client-profile.json", "README.md",
          "_pipeline/build/_scratch", "_pipeline/data"):
    assert os.path.exists(os.path.join(ws, p)), f"missing {p}"
assert not os.path.exists(os.path.join(ws, "_pipeline", "template")), "template nested under _pipeline"
assert not os.path.exists(os.path.join(ws, "_pipeline", "scripts", "node_modules")), "node_modules copied"
assert os.access(os.path.join(ws, "_pipeline", "scripts", "build_master.py"), os.W_OK)
# a second run keeps the filled-in files and refreshes the scripts
claude = os.path.join(ws, "_pipeline", "CLAUDE.md")
open(claude, "a", encoding="utf-8").write("\nFILLED IN\n")
script = os.path.join(ws, "_pipeline", "scripts", "run_pipeline.sh")
open(script, "w").write("broken")
r = subprocess.run([bash, "init_workspace.sh", ws], capture_output=True, text=True)
assert r.returncode == 0 and "existing workspace" in r.stdout, r.stdout + r.stderr
assert "FILLED IN" in open(claude, encoding="utf-8").read()
assert open(script).read() != "broken", "scripts not refreshed from the plugin"
# re-run from a package: data comes from the zip, scripts from the plugin
pkg = os.path.join(d, "pkg.zip")
with zipfile.ZipFile(pkg, "w") as z:
    z.writestr("_pipeline/CLAUDE.md", "FROM PACKAGE")
    z.writestr("_pipeline/data/drafted_items.json", "[]")
    z.writestr("_pipeline/scripts/run_pipeline.sh", "stale")
    z.writestr("_pipeline/build/report.config.json", "{}")
ws2 = os.path.join(d, "ws2")
r = subprocess.run([bash, "init_workspace.sh", ws2, "--from-package", pkg], capture_output=True, text=True)
assert r.returncode != 0, "a package with no assets must fail the layout check\n" + r.stdout
assert open(os.path.join(ws2, "_pipeline", "CLAUDE.md"), encoding="utf-8").read() == "FROM PACKAGE"
assert open(os.path.join(ws2, "_pipeline", "scripts", "run_pipeline.sh")).read() != "stale"
# from a workspace copy there is nothing to stamp from: refuse, do not guess
r = subprocess.run([bash, os.path.join(ws, "_pipeline", "scripts", "init_workspace.sh"), os.path.join(d, "ws3")],
                   capture_output=True, text=True)
assert r.returncode != 0 and "PLUGIN" in r.stdout + r.stderr, r.stdout + r.stderr
PYCHECK
fi

# Behavioural checks on the pure-stdlib helpers, so a regression in the merge or
# protection logic is caught here and not on a live report.
"$PY" - <<'PYCHECK' 2>&1 && ok "build_master.py: merges block, origin protection, photo_mode, pin date, deleted_pins decision, omit, voice guard" \
    || bad "build_master.py behavioural check failed"
import json, os, subprocess, sys, tempfile
d = tempfile.mkdtemp()
items = [
  {"number": 1, "photos": [{"uid": "a", "title": "20260101_100000_a", "captured": "20260101T100000", "path": "/p/a__20260101_100000_a.jpg"}],
   "sheet_name": "TO2-01A", "sheet_description": "Plan", "room": "", "status": "open", "created_at": "2025-12-31T18:05:00.000+00:00"},
  {"number": 2, "photos": [{"uid": "b", "title": "20260101_090000_b", "captured": "20260101T090000", "path": "/p/b__20260101_090000_b.jpg"}],
   "sheet_name": "T02-01A", "sheet_description": "Plan", "room": "", "status": "open", "created_at": "2025-12-31T18:06:00"},
  {"number": 3, "photos": [], "sheet_name": None, "sheet_description": None, "room": "", "status": "open",
   "created_at": "2026-01-02", "deleted_in_plangrid": True},
]
drafted = {"items": [
  {"number": 1, "title": "Alpha", "description": "Conduit stubbed up.", "corrective_action": "fix it",
   "origin": "photo_inferred", "confidence": "low"},
  {"number": 3, "title": "Gamma", "description": "Approved text, kept verbatim.",
   "corrective_action": "leave as is", "origin": "user_reviewed", "photo_mode": "none"},
], "merges": [{"into": 1, "from": 2}]}
json.dump(items, open(os.path.join(d, "items.json"), "w", encoding="utf-8"))
json.dump(drafted, open(os.path.join(d, "drafted.json"), "w", encoding="utf-8"))
# deleted pins: the decision lives in report.config.json beside the output (0.9.0)
json.dump({"deleted_pins": "keep"}, open(os.path.join(d, "report.config.json"), "w", encoding="utf-8"))
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
assert m["#1"]["date_recorded"] == "12/31/2025", m["#1"]     # the PIN's date, not the photo's (01/01)
assert m["#3"]["date_recorded"] == "01/02/2026" and m["#3"]["deleted_in_plangrid"] is True
assert m["#1"]["deleted_in_plangrid"] is False
assert "date recorded  : 2 from pin created_at" in r.stdout and "deleted, kept  : ['#3']" in r.stdout, r.stdout
# the voice guard bans narration, not the noun: an absence-of-evidence sentence passes,
# "the photograph shows" does not, and verify_report.py uses the same list
import importlib.util
spec = importlib.util.spec_from_file_location("bm", "build_master.py"); bm = importlib.util.module_from_spec(spec); spec.loader.exec_module(bm)
spec = importlib.util.spec_from_file_location("vr", "verify_report.py"); vr = importlib.util.module_from_spec(spec); spec.loader.exec_module(vr)
assert vr.VOICE_BANNED is bm.VOICE_BANNED or vr.VOICE_BANNED == bm.VOICE_BANNED, "verify_report.py voice list diverged"
import re as _re
hit = lambda s: any(_re.search(p, s, _re.I) for p in bm.VOICE_BANNED)
for ok_text in ("The field note reads only Up, with no accompanying photograph.",
                "No photographs were taken at this pin; condition requires field verification.",
                "Cable tray is not bonded to the building grounding system.",
                "The rack frame is bent at the base.", "The door frame is damaged at the strike."):
    assert not hit(ok_text), ok_text
for bad_text in ("The photograph shows an open junction box.", "Conduit is visible in the frame.",
                 "As seen in the image, the tray is unsupported.", "In the photo the box is open.",
                 "The field engineer recorded the condition.", "This photo captures the stub.",
                 # 0.9.0: statements about the photo or the note, not the site
                 "The image is unclear.", "The photos are too dark to read the label.",
                 "Image unclear.", "The note says the box is missing.", "Per the pin note, conduit is open.",
                 "The pin note requests confirmation of the ground bar.", "The pin note records a missing cover.",
                 "The pin flags a conduit to be relocated."):
    assert hit(bad_text), bad_text
# a spaced dash becomes ", " (not " ,"), a numeric range keeps a hyphen
assert bm.sanitize("Switch Cabinet Position – Cabinets 201 & 202") == "Switch Cabinet Position, Cabinets 201 & 202"
assert bm.sanitize("Rows 10–12") == "Rows 10-12" and bm.sanitize("Open box—no cover") == "Open box, no cover"
drafted["items"][0]["description"] = "Pin note reads Up, with no accompanying photograph."
json.dump(drafted, open(os.path.join(d, "drafted.json"), "w", encoding="utf-8"))
r = subprocess.run([sys.executable, "build_master.py", "--items", os.path.join(d, "items.json"),
                    "--drafted", os.path.join(d, "drafted.json"), "-o", out], capture_output=True, text=True)
assert r.returncode == 0, "absence-of-photo sentence must pass the build\n" + r.stdout + r.stderr
drafted["items"][0]["description"] = "The photograph shows conduit stubbed up."
json.dump(drafted, open(os.path.join(d, "drafted.json"), "w", encoding="utf-8"))
r = subprocess.run([sys.executable, "build_master.py", "--items", os.path.join(d, "items.json"),
                    "--drafted", os.path.join(d, "drafted.json"), "-o", out], capture_output=True, text=True)
assert r.returncode != 0 and "#1" in r.stdout + r.stderr, "narration must fail the build"
drafted["items"][0]["description"] = "Conduit stubbed up."
# a protected entry that sanitize would alter must fail the build
drafted["items"][1]["description"] = "bad \u2014 dash"
json.dump(drafted, open(os.path.join(d, "drafted.json"), "w", encoding="utf-8"))
r = subprocess.run([sys.executable, "build_master.py", "--items", os.path.join(d, "items.json"),
                    "--drafted", os.path.join(d, "drafted.json"), "-o", out],
                   capture_output=True, text=True)
assert r.returncode != 0 and "not sanitize-clean" in (r.stdout + r.stderr)
drafted["items"][1]["description"] = "Approved text, kept verbatim."
json.dump(drafted, open(os.path.join(d, "drafted.json"), "w", encoding="utf-8"))
# 0.9.0: deleted pins are dropped by default at THIS step (consolidate keeps them
# all), so the decision is a re-render; "omit" drops a pin without touching items.json
json.dump({}, open(os.path.join(d, "report.config.json"), "w", encoding="utf-8"))
r = subprocess.run([sys.executable, "build_master.py", "--items", os.path.join(d, "items.json"),
                    "--drafted", os.path.join(d, "drafted.json"), "-o", out], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
assert [x["plangrid_ref"] for x in json.load(open(out, encoding="utf-8"))] == ["#1"], "deleted pin must drop by default"
assert "deleted, dropped: ['#3']" in r.stdout, r.stdout
json.dump({"deleted_pins": "keep"}, open(os.path.join(d, "report.config.json"), "w", encoding="utf-8"))
drafted["omit"] = [3]
json.dump(drafted, open(os.path.join(d, "drafted.json"), "w", encoding="utf-8"))
r = subprocess.run([sys.executable, "build_master.py", "--items", os.path.join(d, "items.json"),
                    "--drafted", os.path.join(d, "drafted.json"), "-o", out], capture_output=True, text=True)
assert r.returncode == 0 and [x["plangrid_ref"] for x in json.load(open(out, encoding="utf-8"))] == ["#1"], r.stdout + r.stderr
# keeping a deleted pin that has no draft names it plainly
drafted = {"items": [drafted["items"][0]], "merges": [{"into": 1, "from": 2}]}
json.dump(drafted, open(os.path.join(d, "drafted.json"), "w", encoding="utf-8"))
r = subprocess.run([sys.executable, "build_master.py", "--items", os.path.join(d, "items.json"),
                    "--drafted", os.path.join(d, "drafted.json"), "-o", out], capture_output=True, text=True)
assert r.returncode != 0 and "deleted_pins=keep" in r.stdout + r.stderr, r.stdout + r.stderr
PYCHECK

"$PY" - <<'PYCHECK' 2>&1 && ok "consolidate.py: multi-delta layering, scope rules, --keep-deleted" \
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
# scope rules: exact record-only phrase dropped, near miss kept and reported,
# title and date filters, archived always dropped
d2 = tempfile.mkdtemp()
rows = [
  dict(t(10, "a", "Observation only for record"), title="Visit 2", created_at="2026-09-03T10:00:00"),
  dict(t(11, "b", "Observation only, ignore."), title="Visit 2", created_at="2026-09-03T10:00:00"),
  dict(t(12, "c", "Missing box"), title="Visit 2", created_at="2026-09-03T10:00:00"),
  dict(t(13, "d", "Missing box"), title="General", created_at="2026-09-03T10:00:00"),
  dict(t(14, "e", "Missing box"), title="Visit 2", created_at="2026-08-20T10:00:00"),
  dict(t(15, "f", "Missing box"), title="Visit 2", created_at="2026-09-03T10:00:00", archived=True),
  dict(t(16, "g", "Up"), title="Visit 2", created_at="2026-09-03T10:00:00", deleted=True),
]
os.makedirs(os.path.join(d2, "photos")); json.dump(rows, open(os.path.join(d2, "tasks.json"), "w"))
json.dump([], open(os.path.join(d2, "sheets.json"), "w"))
# two kept items pointing at the same photo uid: the shared-photo duplicate signal
os.makedirs(os.path.join(d2, "task_details"))
open(os.path.join(d2, "photos", "p1__20260903_100000_x.jpg"), "wb").write(b"\xff\xd8\xff\xd9")
for uid in ("b", "c"):
    json.dump({"task_uid": uid, "photos": [{"uid": "p1", "title": "20260903_100000_x", "created_by": {"email": "e"}}]},
              open(os.path.join(d2, "task_details", uid + ".json"), "w"))
out2 = os.path.join(d2, "items.json")
r = subprocess.run([sys.executable, "consolidate.py", d2, "-o", out2, "--drop-phrase", "Observation only for record",
                    "--title", "Visit 2", "--created-after", "2026-08-31"], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
got = {i["number"]: i for i in json.load(open(out2, encoding="utf-8"))}
assert sorted(got) == [11, 12], sorted(got)
assert "NEAR-MISS" in r.stdout and "#11" in r.stdout, r.stdout
assert got[11]["possible_duplicate"] == [12] and got[12]["possible_duplicate"] == [11], got
assert got[11]["deleted_in_plangrid"] is False
tri = json.load(open(os.path.join(d2, "triage.json"), encoding="utf-8"))
assert tri["possible_duplicates"] == [[11, 12]], tri
assert tri["dropped_deleted_or_archived"] == [15, 16] and tri["kept_deleted_marked"] == [], tri
# --keep-deleted: the intake decision "keep, marked". Deleted and archived pins
# stay, flagged, and still obey the other scope rules.
out3 = os.path.join(d2, "items_keep.json")
r = subprocess.run([sys.executable, "consolidate.py", d2, "-o", out3, "--drop-phrase", "Observation only for record",
                    "--title", "Visit 2", "--created-after", "2026-08-31", "--keep-deleted"], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
got = {i["number"]: i for i in json.load(open(out3, encoding="utf-8"))}
assert sorted(got) == [11, 12, 15, 16], sorted(got)
assert got[15]["deleted_in_plangrid"] is True and got[16]["deleted_in_plangrid"] is True and got[12]["deleted_in_plangrid"] is False
assert "kept, deleted/archived (marked deleted_in_plangrid) : [15, 16]" in r.stdout, r.stdout
tri = json.load(open(os.path.join(d2, "triage.json"), encoding="utf-8"))
assert tri["kept_deleted_marked"] == [15, 16] and tri["rules"]["keep_deleted"] is True, tri
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

# Render a one-item fixture end to end and check the two defects only Word
# rejects: a literal <undefined> element (docx@9.7.1 ImportedXmlComponent bug)
# and duplicate wp:docPr ids (docx@9.7.1 DocProperties bug). Both shipped to a
# reviewer once (2026-09-09) with verify_report.py passing 16/16, because the
# checks lived only in a session workspace. They now live here.
if node -e 'require("docx")' >/dev/null 2>&1; then
"$PY" - <<'PYCHECK' 2>&1 && ok "gen_report.js: fixture renders, pin dates, deleted banner, visit sections, no <undefined>, unique wp:docPr ids, verify passes" \
    || bad "gen_report.js render check failed"
import json, os, re, shutil, subprocess, sys, tempfile, zipfile
here = os.getcwd()
assets = None
for cand in ("../template/_pipeline/build/assets", "../build/assets"):
    if os.path.isdir(os.path.join(here, cand, "logos")):
        assets = os.path.join(here, cand)
        break
assert assets, "no assets/logos folder found (expected ../template/_pipeline/build/assets or ../build/assets)"
d = os.path.join(tempfile.mkdtemp(), "_pipeline"); os.makedirs(d)   # README sits one level up, as in a workspace
shutil.copytree(assets, os.path.join(d, "assets"))
os.makedirs(os.path.join(d, "thumbs_uniform"))
os.makedirs(os.path.join(d, "sheet_clips_jpg"))
# Two visit dates, the second item deleted in PlanGrid and kept (intake "keep, marked").
items = [{"number": 1, "photos": [], "sheet_name": "T02-01A", "sheet_description": "Plan",
          "room": "", "status": "open", "created_at": "2026-01-01T10:00:00"},
         {"number": 2, "photos": [], "sheet_name": "T02-01A", "sheet_description": "Plan",
          "room": "", "status": "open", "created_at": "2026-01-02T09:30:00", "deleted_in_plangrid": True}]
drafted = {"items": [{"number": 1, "title": "Alpha", "description": "Conduit stubbed up.",
                      "corrective_action": "Cap it.", "origin": "authored", "photo_mode": "none"},
                     {"number": 2, "title": "Beta", "description": "Pin carries no usable content.",
                      "corrective_action": "None.", "origin": "authored", "photo_mode": "none"}]}
json.dump(items, open(os.path.join(d, "items.json"), "w", encoding="utf-8"))
json.dump(drafted, open(os.path.join(d, "drafted.json"), "w", encoding="utf-8"))
json.dump({"deleted_pins": "keep"}, open(os.path.join(d, "report.config.json"), "w", encoding="utf-8"))
master = os.path.join(d, "master_report_items.json")
r = subprocess.run([sys.executable, "build_master.py", "--items", os.path.join(d, "items.json"),
                    "--drafted", os.path.join(d, "drafted.json"), "-o", master],
                   capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
json.dump({"master_file": "master_report_items.json", "output_filename": "fixture.docx",
           "cover_mode": "template", "cover_eyebrow": "Technology Site Inspection",
           "cover_subtitle": "Building X", "client_display_name": "Fixture Client Project",
           "site_address": ["1 Fixture St.,", "Town, ST"], "ep_project_no": "99999",
           "inspection_date": ["2026-01-01", "2026-01-02"], "issuance_date": "2026-01-03", "inspector": "Fixture",
           "visit_sections": "by_date", "deleted_pins": "keep"},
          open(os.path.join(d, "report.config.json"), "w", encoding="utf-8"))
json.dump({}, open(os.path.join(d, "sheet_clip_dims_jpg.json"), "w", encoding="utf-8"))
r = subprocess.run(["node", "gen_report.js", d], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
assert "visit_sections=2 deleted_marked=1" in r.stdout and "DATE_RECORDED_MISSING" not in r.stdout, r.stdout
out = os.path.join(d, "fixture.docx")
x = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")
assert "<undefined" not in x, "literal <undefined> element rendered: gen_report.js lost the importXml() unwrap"
ids = re.findall(r'<wp:docPr[^>]*\bid="(\d+)"', x)
assert len(ids) == len(set(ids)), f"duplicate wp:docPr ids: {ids}"  # body may hold no images at all
assert x.count("<w:sectPr") == 2, "body must carry a blank first section in template mode"
body_text = re.sub(r"\s+", " ", " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", x)))
assert "99999" not in body_text, "EP project number leaked into the body"
assert "Date Recorded 01/01/2026" in body_text and "Date Recorded 01/02/2026" in body_text, body_text[-600:]
assert "Date Recorded N/A" not in body_text, "pin date not used for Date Recorded"
assert body_text.count("DELETED IN PLANGRID.") == 1, "deleted banner missing or repeated"
assert "(deleted in PlanGrid)" in body_text, "TOC entry not marked for the deleted pin"
assert "Site Visit 1, 01/01/2026" in body_text and "Site Visit 2, 01/02/2026" in body_text, "visit headings missing"
assert len(re.findall(r"PAGEREF\s+\w+", x)) == 4, "TOC must list 2 items + 2 visit sections"
assert x.count("<w:pageBreakBefore/>") == 2, "one page break per item (carried by the visit heading)"
# a break naming an item that is not in the master must fail the render, not render flat
cfg = json.load(open(os.path.join(d, "report.config.json"), encoding="utf-8"))
cfg["visit_breaks"] = [{"before": 1, "title": "A"}, {"before": 99, "title": "B"}]
json.dump(cfg, open(os.path.join(d, "report.config.json"), "w", encoding="utf-8"))
r2 = subprocess.run(["node", "gen_report.js", d, os.path.join(d, "bad.docx")], capture_output=True, text=True)
assert r2.returncode != 0 and "99" in r2.stderr, "bad visit_breaks must fail loudly"
del cfg["visit_breaks"]
json.dump(cfg, open(os.path.join(d, "report.config.json"), "w", encoding="utf-8"))
# issuance date TBD is the sanctioned draft placeholder; the cover check must accept it
cfg_tbd = dict(cfg, issuance_date="TBD", output_filename="tbd.docx")
json.dump(cfg_tbd, open(os.path.join(d, "report.config.json"), "w", encoding="utf-8"))
r3 = subprocess.run(["node", "gen_report.js", d], capture_output=True, text=True)
assert r3.returncode == 0, r3.stdout + r3.stderr
subprocess.run([sys.executable, "fix_bookmark_ids.py", os.path.join(d, "tbd.docx")], capture_output=True, text=True)
r3 = subprocess.run([sys.executable, "verify_report.py", os.path.join(d, "tbd.docx"), master], capture_output=True, text=True)
assert r3.returncode == 0 and "issuance date TBD" in r3.stdout, "TBD issuance date must verify\n" + r3.stdout + r3.stderr
json.dump(cfg, open(os.path.join(d, "report.config.json"), "w", encoding="utf-8"))
cz = zipfile.ZipFile(os.path.join(d, "fixture-Cover.docx"))
cx = cz.read("word/document.xml").decode("utf-8")
ctext = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", cx)).replace("&amp;", "&")
assert "<undefined" not in cx
cids = re.findall(r'<wp:docPr[^>]*\bid="(\d+)"', cx)
assert cids and len(cids) == len(set(cids)), f"duplicate wp:docPr ids in cover: {cids}"
for needle in ("99999", "Building X", "Fixture Client Project", "01/01/2026 & 01/02/2026", "01/03/2026", "Technology Site Inspection"):
    assert needle in ctext, f"cover missing {needle!r}"
assert "DRAFT" not in ctext.upper(), "draft warning must not be on the cover"
assert not any(re.match(r"word/header\d*\.xml$", n) for n in cz.namelist()), "cover must have no letterhead header"
fx = zipfile.ZipFile(out).read("word/footer1.xml").decode("utf-8") if "word/footer1.xml" in zipfile.ZipFile(out).namelist() else ""
assert "Technology System Punch List" in " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", fx)), "footer wording not derived"
r = subprocess.run([sys.executable, "fix_bookmark_ids.py", out], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
r = subprocess.run([sys.executable, "verify_report.py", out, master], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
open(os.path.join(d, "verify_output.txt"), "w", encoding="utf-8").write(r.stdout)
# the run record reads the same artifacts and must never need a hand-typed number
r = subprocess.run([sys.executable, "run_record.py", "--pipeline", d, "--build", ".", "--data", ".", "--no-docs"],
                   capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
# the CLAUDE.md current-output line is replaced whole, even when a template wrapped it
open(os.path.join(d, "CLAUDE.md"), "w", encoding="utf-8").write(
    "# X\n\n**Current output:** `<f>.docx`, <N> items, <N> sheet\nclips. Draft.\n\n## Next\n")
r = subprocess.run([sys.executable, "run_record.py", "--pipeline", d, "--build", ".", "--data", "."],
                   capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
cm = open(os.path.join(d, "CLAUDE.md"), encoding="utf-8").read()
assert "clips. Draft.\n" not in cm and "fixture.docx" in cm and "## Next" in cm, cm
# identity placeholders are filled from the config and the artifacts; judgment ones are not
shutil.copy(out, os.path.join(d, "Proj-Bldg-Punch-Report-DRAFT-v0.3.docx"))      # newest render, carries the version
open(os.path.join(d, "ISSUES-LIST.md"), "w", encoding="utf-8").write(
    "# Open questions for the reviewer, <PROJECT> v0.1\n\n### Item <N> (PlanGrid #<N>) - <one-line problem>\n")
open(os.path.join(d, "..", "README.md"), "w", encoding="utf-8").write(
    "# <Project>, <Building / area>, punch report\n\nDraft for the <date> walk.\n| `<report>-DRAFT-v0.1.docx` | <N> items, <N> pages, <N> photos |\n\n<What this report covers, what was excluded>\n")
r = subprocess.run([sys.executable, "run_record.py", "--pipeline", d, "--build", ".", "--data", "."],
                   capture_output=True, text=True)
assert r.returncode == 0 and "placeholders" in r.stdout, r.stdout + r.stderr
il = open(os.path.join(d, "ISSUES-LIST.md"), encoding="utf-8").read()
assert il.startswith("# Open questions for the reviewer, Building X v0.3"), il
assert "### Item <N> (PlanGrid #<N>)" in il, "judgment placeholder must be left for a person"
rd = open(os.path.join(d, "..", "README.md"), encoding="utf-8").read()
assert rd.startswith("# Building X, Building X, punch report") and "2026-01-01 and 2026-01-02 walk" in rd, rd
assert "Proj-Bldg-Punch-Report-DRAFT-v0.3.docx" in rd and "2 items, 0 photos" in rd and "<What this report covers" in rd, rd
rec = json.load(open(os.path.join(d, "run.json"), encoding="utf-8"))
assert rec["counts"]["clip_missing"] == [1, 2], rec["counts"]   # keyed by item_<N>.jpg, none exist here
assert rec["counts"]["items"] == 2 and rec["output"]["verified"] is True, rec
assert rec["counts"]["deleted_retained"] == [2] and rec["counts"]["pin_dates"] == ["2026-01-01", "2026-01-02"], rec["counts"]
# the review sheet lands in the build folder under the report's stem, by default
r = subprocess.run([sys.executable, "review_sheet.py", "export", d], capture_output=True, text=True)
assert r.returncode == 0 and os.path.isfile(os.path.join(d, "fixture-Review.xlsx")), r.stdout + r.stderr
cfg["output_filename"] = "Proj-Bldg-Punch-Report-DRAFT-v0.3.docx"
json.dump(cfg, open(os.path.join(d, "report.config.json"), "w", encoding="utf-8"))
r = subprocess.run([sys.executable, "review_sheet.py", "export", d], capture_output=True, text=True)
assert r.returncode == 0 and os.path.isfile(os.path.join(d, "Proj-Bldg-Punch-Report-Review.xlsx")), r.stdout + r.stderr
from openpyxl import load_workbook
ws = load_workbook(os.path.join(d, "Proj-Bldg-Punch-Report-Review.xlsx")).active
hdr = [c.value for c in ws[1]]
row2 = [c.value for c in ws[3]]
assert row2[hdr.index("Date Recorded")] == "01/02/2026" and row2[hdr.index("Deleted in PlanGrid")] == "Y", row2
shutil.rmtree(d, ignore_errors=True)
PYCHECK
else
    bad "gen_report.js render check skipped: docx package not installed (bash scripts/install_deps.sh)"
fi

# 0.9.0 build first, finish later. locate_inputs.py picks the project folder and
# the version without asking; prefill_config.py fills the cover from sources on
# record only; a draft with gaps renders red [MISSING: ...] markers, verifies,
# and finish_list.py names one update_report.py command per gap; update_report.py
# then edits surgically, re-renders, and delivers the next version beside the last.
"$PY" - <<'PYCHECK' 2>&1 && ok "locate_inputs.py: project folder by hint or the only one, next version from the folder, none means outputs" \
    || bad "locate_inputs.py behavioural check failed"
import json, os, subprocess, sys, tempfile
d = tempfile.mkdtemp(); mnt = os.path.join(d, "mnt")
for p in ("outputs", "uploads", ".local-plugins", "CTX2_v2/pull1", "Other Job"):
    os.makedirs(os.path.join(mnt, p))
open(os.path.join(mnt, "CTX2_v2", "pull1", "tasks.json"), "w").write("[]")
open(os.path.join(mnt, "CTX2_v2", "PlanGrid Task Report - Sep 10.pdf"), "wb").write(b"%PDF")
open(os.path.join(mnt, "CTX2_v2", "CTX2-Punch-Report-DRAFT-v0.3.docx"), "wb").write(b"x")
run = lambda *a: subprocess.run([sys.executable, "locate_inputs.py", *a, "--mnt", mnt, "--json"], capture_output=True, text=True)
r = run("ctx2"); assert r.returncode == 0, r.stdout + r.stderr
j = json.loads(r.stdout)
assert j["project_folder"].endswith("CTX2_v2") and j["next_version"] == "0.4", j
assert j["inputs"][j["project_folder"]]["pulls"] and j["inputs"][j["project_folder"]]["task_reports"], j
assert set(os.path.basename(c) for c in j["connected"]) == {"CTX2_v2", "Other Job"}, j["connected"]
r = run(); j = json.loads(r.stdout)
assert j["project_folder"] is None and j["deliver_to"].endswith("outputs"), j   # two connected, no hint: never guess
os.rename(os.path.join(mnt, "Other Job"), os.path.join(mnt, ".hidden"))
j = json.loads(run().stdout)
assert j["project_folder"].endswith("CTX2_v2"), j                                  # the only one connected
os.rename(os.path.join(mnt, "CTX2_v2"), os.path.join(mnt, ".gone"))
j = json.loads(run("ctx2").stdout)
assert j["project_folder"] is None and j["next_version"] == "0.1", j               # nothing connected
PYCHECK

# Needs the plugin checkout (the template beside scripts/), like the stamper check;
# from a workspace copy (test-punch step 2) it is skipped, not failed.
if [ ! -d ../template/_pipeline ]; then
    :
elif node -e 'require("docx")' >/dev/null 2>&1; then
"$PY" - <<'PYCHECK' 2>&1 && ok "build first: prefill from records, [MISSING] on the cover, finish list, update_report edits, re-render, deliver v0.1 then v0.2" \
    || bad "build-first flow check failed"
import json, os, re, subprocess, sys, tempfile, time, zipfile
bash = os.environ.get("SMOKE_BASH") or "bash"
here = os.getcwd()
d = tempfile.mkdtemp(); mnt = os.path.join(d, "mnt")
os.makedirs(os.path.join(mnt, "outputs")); os.makedirs(os.path.join(mnt, "Proj"))
ws = os.path.join(mnt, "outputs", "ctx2-punch")
r = subprocess.run([bash, "init_workspace.sh", ws], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
pipe = os.path.join(ws, "_pipeline")
env = dict(os.environ, PYTHONUTF8="1", NODE_PATH=os.path.join(here, "node_modules"), PIPELINE_BASH=bash)
items = [{"number": 1, "photos": [], "sheet_name": "T02-01A", "sheet_description": "Plan", "room": "", "status": "open",
          "created_at": "2026-08-27T10:00:00", "created_by": "leo.manning@eplusadvisors.com", "description": "Open box"},
         {"number": 2, "photos": [], "sheet_name": "T02-01A", "sheet_description": "Plan", "room": "", "status": "open",
          "created_at": "2026-08-28T09:00:00", "created_by": "leo.manning@eplusadvisors.com", "description": "Up",
          "deleted_in_plangrid": True}]
json.dump(items, open(os.path.join(pipe, "data", "items.json"), "w", encoding="utf-8"))
json.dump({"near_miss": [[1, "Observation only, ignore."]]}, open(os.path.join(pipe, "data", "triage.json"), "w"))
json.dump({"items": [{"number": 1, "title": "Open Junction Box", "description": "Junction box is open with no cover.",
                      "corrective_action": "Install the cover.", "origin": "authored", "confidence": "high",
                      "photo_mode": "none"}]},
          open(os.path.join(pipe, "data", "drafted_items.json"), "w", encoding="utf-8"))
py = lambda *a: subprocess.run([sys.executable, *a], cwd=pipe, env=env, capture_output=True, text=True)
# the data-only run records BEFORE prefill; a template hint must never become the project name
r = py("scripts/run_record.py")
assert r.returncode == 0, r.stdout + r.stderr
assert "<PlanGrid project name" not in open(os.path.join(pipe, "ISSUES-LIST.md"), encoding="utf-8").read().splitlines()[0]
r = py("scripts/prefill_config.py", "--project-name", "CTX2", "--version", "v0.1")   # "v0.1" as locate_inputs prints it
assert r.returncode == 0, r.stdout + r.stderr
cfg = json.load(open(os.path.join(pipe, "build", "report.config.json"), encoding="utf-8"))
src = cfg["fact_sources"]
assert cfg["output_filename"] == "CTX2-Punch-Report-DRAFT-v0.1.docx" and cfg["issuance_date"] == "TBD", cfg
assert cfg["inspector"] == "Leo Manning" and "confirm" in src["inspector"], src          # a guess, flagged
assert cfg["client_display_name"] == "" and src["client_display_name"] == "missing", src  # never invented
assert cfg["inspection_date"] == ["2026-08-27", "2026-08-28"] and cfg["deleted_pins"] == "drop", cfg
r = subprocess.run([bash, "scripts/run_pipeline.sh"], cwd=pipe, env=dict(env, RENDER_ONLY="1"), capture_output=True, text=True)
assert r.returncode == 0, r.stdout[-2500:] + r.stderr[-1500:]
assert "all checks passed" in r.stdout and "To finish this report" in r.stdout, r.stdout[-2000:]
cz = zipfile.ZipFile(os.path.join(pipe, "build", "CTX2-Punch-Report-DRAFT-v0.1-Cover.docx"))
ct = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", cz.read("word/document.xml").decode("utf-8")))
for needle in ("[MISSING: client name]", "[MISSING: site address]", "[MISSING: EP project number]",
               "[MISSING: building or area]", "TBD", "Leo Manning", "08/27/2026 &amp; 08/28/2026"):
    assert needle in ct, (needle, ct)
assert "&lt;" not in ct, "template hint text on the cover"
fin = json.load(open(os.path.join(pipe, "build", "finish.json"), encoding="utf-8"))
blocking = {e["what"] for e in fin["blocking"]}
for w in ("Client name", "Site address", "EP project number", "Building or area (cover subtitle)",
          "Inspector (who walked it)", "Issuance date", "Drawing pin clips", "Delivery"):
    assert w in blocking, (w, blocking)
review = " ".join(e["detail"] + " " + (e["command"] or "") for e in fin["review"])
assert "#2 left out" in review and "--deleted-pins keep" in review and "--drop 1" in review, review
il = open(os.path.join(pipe, "ISSUES-LIST.md"), encoding="utf-8").read()
assert "<!-- finish-list:start -->" in il and il.startswith("# Open questions for the reviewer, CTX2 v0.1"), il[:200]
m = json.load(open(os.path.join(pipe, "build", "master_report_items.json"), encoding="utf-8"))
assert [x["plangrid_ref"] for x in m] == ["#1"], m                                       # deleted pin dropped by default
# surgical: the user supplies the cover facts; one command, re-render, no data steps
t = time.time()
r = py("scripts/update_report.py", "--set", "client_display_name=ServerFarm CTX2", "--set", "ep_project_no=27625",
       "--set", "site_address=15515 Cutten Road, | Houston, TX", "--set", "cover_subtitle=Data Hall 1",
       "--set", "inspector=Leo Manning", "--set", "issuance_date=09/30/2026", "--mnt-glob", os.path.join(d, "*"))
assert r.returncode == 0, r.stdout + r.stderr
assert "render only" in open(os.path.join(pipe, "build", "update_render.log"), encoding="utf-8").read()
cz = zipfile.ZipFile(os.path.join(pipe, "build", "CTX2-Punch-Report-DRAFT-v0.1-Cover.docx"))
ct = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", cz.read("word/document.xml").decode("utf-8")))
assert "[MISSING" not in ct and "27625" in ct and "ServerFarm CTX2" in ct and "09/30/2026" in ct, ct
cfg = json.load(open(os.path.join(pipe, "build", "report.config.json"), encoding="utf-8"))
assert cfg["fact_sources"]["ep_project_no"] == "user" and cfg["site_address"] == ["15515 Cutten Road,", "Houston, TX"], cfg
prof = json.load(open(os.path.join(ws, "client-profile.json"), encoding="utf-8"))
assert prof["ep_project_no"] == "27625" and prof["inspector"]["name"] == "Leo Manning", prof   # for the next report
assert "set ep_project_no=27625" in open(os.path.join(pipe, "PROCESS-LOG.md"), encoding="utf-8").read()
fin = json.load(open(os.path.join(pipe, "build", "finish.json"), encoding="utf-8"))
assert {e["what"] for e in fin["blocking"]} == {"Drawing pin clips", "Delivery"}, fin["blocking"]
# keeping the deleted pin is a re-render; with no draft for it the error says so
r = py("scripts/update_report.py", "--deleted-pins", "keep")
assert r.returncode != 0 and "deleted_pins=keep" in r.stdout + r.stderr, r.stdout + r.stderr
r = py("scripts/update_report.py", "--deleted-pins", "keep", "--item", "2", "--title", "Unlabeled Pin",
       "--description", "Pin note reads only Up — nothing further recorded.", "--photo-mode", "none")
assert r.returncode == 0, r.stdout + r.stderr
# a batch file keyed by "item" instead of "number" is accepted
json.dump([{"item": 1, "title": "Open Junction Box – Level 1"}], open(os.path.join(pipe, "build", "_scratch", "edits.json"), "w"))
r = py("scripts/update_report.py", "--edits", "build/_scratch/edits.json")
assert r.returncode == 0, r.stdout + r.stderr
m1 = json.load(open(os.path.join(pipe, "build", "master_report_items.json"), encoding="utf-8"))[0]
assert m1["title"] == "Open Junction Box, Level 1", m1["title"]
m = json.load(open(os.path.join(pipe, "build", "master_report_items.json"), encoding="utf-8"))
assert [x["plangrid_ref"] for x in m] == ["#1", "#2"] and m[1]["deleted_in_plangrid"] is True, m
assert m[1]["origin"] == "user_reviewed" and "—" not in m[1]["description"], m[1]      # dashes cleaned on the way in
# delivery: paperwork written, then v0.1 to the project folder, then a change delivers v0.2 beside it
for rel, marker in (("_pipeline/PROCESS-LOG.md", "<What was included, what was excluded"),
                    ("_pipeline/PROCESS-LOG.md", "- Tools used and roughly how many calls"),
                    ("_pipeline/ISSUES-LIST.md", "### Item <N> (PlanGrid #<N>)"),
                    ("README.md", "<What this report covers, what was excluded"),
                    ("_pipeline/CLAUDE.md", "<State what was excluded and by whose direction")):
    p = os.path.join(ws, rel); s = open(p, encoding="utf-8").read()
    open(p, "w", encoding="utf-8").write(s.replace(marker, "Written for the test."))
r = py("scripts/update_report.py", "--deliver", "Proj", "--mnt-glob", os.path.join(d, "*"))
assert r.returncode == 0, r.stdout + r.stderr
assert os.path.isfile(os.path.join(mnt, "Proj", "CTX2-Punch-Report-DRAFT-v0.1.docx")), os.listdir(os.path.join(mnt, "Proj"))
assert json.load(open(os.path.join(pipe, "build", "report.config.json"), encoding="utf-8"))["delivery_folder"] == "Proj"
fin = json.load(open(os.path.join(pipe, "build", "finish.json"), encoding="utf-8"))
assert "Delivery" not in {e["what"] for e in fin["blocking"]}, fin["blocking"]
r = py("scripts/update_report.py", "--set", "issuance_date=2026-10-01", "--deliver", "--mnt-glob", os.path.join(d, "*"))
assert r.returncode == 0, r.stdout + r.stderr
got = sorted(os.listdir(os.path.join(mnt, "Proj")))
assert "CTX2-Punch-Report-DRAFT-v0.1.docx" in got and "CTX2-Punch-Report-DRAFT-v0.2.docx" in got \
    and "CTX2-Punch-Report-DRAFT-v0.2-Cover.docx" in got and "CTX2-Punch-Report-DRAFT-v0.2.zip" in got, got
# the review sheet of v0.2 is delivered under the versioned name, not left stale behind v0.1's
assert "CTX2-Punch-Report-Review.xlsx" in got and "CTX2-Punch-Report-DRAFT-v0.2-Review.xlsx" in got, got
assert "version CTX2-Punch-Report-DRAFT-v0.1.docx -> CTX2-Punch-Report-DRAFT-v0.2.docx" in r.stdout, r.stdout
# an unconnected folder is refused with the list of what is connected, never a picker
r = py("scripts/update_report.py", "--deliver", "Nowhere", "--no-render", "--mnt-glob", os.path.join(d, "*"))
assert r.returncode != 0 and "not connected" in r.stdout + r.stderr and "Proj" in r.stdout + r.stderr, r.stdout + r.stderr
print(f"update round trip {time.time() - t:.0f} s")
PYCHECK
else
    bad "build-first flow check skipped: docx package not installed (bash scripts/install_deps.sh)"
fi

# package.py: the zip carries the workspace and nothing that was superseded
# during the run; re-delivery suffixes by default and overwrites only with
# --replace.
"$PY" - <<'PYCHECK' 2>&1 && ok "package.py: clean manifest (no strays, no earlier renders, no duplicate photos), suffix vs --replace" \
    || bad "package.py behavioural check failed"
import os, subprocess, sys, tempfile, time, zipfile
d = tempfile.mkdtemp(); ws = os.path.join(d, "ws"); dest = os.path.join(d, "project"); os.makedirs(dest)
def w(rel, data=b"x"):
    p = os.path.join(ws, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "wb").write(data); return p
w("_pipeline/CLAUDE.md"); w("_pipeline/PROCESS-LOG.md"); w("client-profile.json", b"{}")
w("_pipeline/data/items.json"); w("_pipeline/data/_write_probe.json")
w("_pipeline/scripts/build_master.py"); w("_pipeline/scripts/_write_probe.py"); w("_pipeline/scripts/node_modules/docx/x.js")
w("_pipeline/template/_pipeline/CLAUDE.md"); w("_pipeline/templates/item-preview.html")
w("_pipeline/build/master_report_items.json"); w("_pipeline/build/master_report_items.json.20260914.bak.json")
w("_pipeline/build/assets/logos/ep_logo.jpg"); w("_pipeline/build/thumbs_uniform/a.jpg"); w("_pipeline/build/sheet_clips_jpg/item_1.jpg")
w("_pipeline/build/_scratch/preview.pdf"); w("_pipeline/build/v0.2/X-DRAFT-v0.2.docx")
w("plangrid_mcp/tasks.json"); w("plangrid_mcp/photos/p.jpg"); w("plangrid_pull/tasks.json"); w("plangrid_pull/photos/p.jpg")
old = w("_pipeline/build/X-DRAFT-v0.1.docx"); w("_pipeline/build/X-DRAFT-v0.1-Cover.docx"); w("_pipeline/build/X-Review-old.xlsx")
time.sleep(1.1)
new = w("_pipeline/build/X-DRAFT-v0.2.docx"); w("_pipeline/build/X-DRAFT-v0.2-Cover.docx"); w("_pipeline/build/X-Review.xlsx")
# unfilled paperwork blocks delivery unless explicitly allowed
w("_pipeline/PROCESS-LOG.md", b"## Scope decision\n\n<What was included, what was excluded, on whose direction>\n")
r = subprocess.run([sys.executable, "package.py", ws, dest], capture_output=True, text=True)
assert r.returncode != 0 and "template text" in r.stdout + r.stderr and not os.listdir(dest), r.stdout + r.stderr
r = subprocess.run([sys.executable, "package.py", ws, dest, "--dry-run"], capture_output=True, text=True)
assert r.returncode == 0 and "WARNING" in r.stdout, r.stdout + r.stderr
w("_pipeline/PROCESS-LOG.md", b"## Scope decision\n\nAll 2 items.\n")
r = subprocess.run([sys.executable, "package.py", ws, dest], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
names = set(zipfile.ZipFile(os.path.join(dest, "X-DRAFT-v0.2.zip")).namelist())
must = {"_pipeline/CLAUDE.md", "_pipeline/data/items.json", "_pipeline/scripts/build_master.py", "client-profile.json",
        "_pipeline/build/master_report_items.json", "_pipeline/build/assets/logos/ep_logo.jpg",
        "_pipeline/build/thumbs_uniform/a.jpg", "_pipeline/build/sheet_clips_jpg/item_1.jpg",
        "_pipeline/build/X-DRAFT-v0.2.docx", "_pipeline/build/X-DRAFT-v0.2-Cover.docx", "_pipeline/build/X-Review.xlsx",
        "plangrid_mcp/tasks.json", "plangrid_pull/tasks.json", "plangrid_pull/photos/p.jpg"}
assert must <= names, must - names
for bad_name in ("_pipeline/data/_write_probe.json", "_pipeline/scripts/_write_probe.py", "_pipeline/scripts/node_modules/docx/x.js",
                 "_pipeline/template/_pipeline/CLAUDE.md", "_pipeline/templates/item-preview.html",
                 "_pipeline/build/master_report_items.json.20260914.bak.json", "_pipeline/build/_scratch/preview.pdf",
                 "_pipeline/build/v0.2/X-DRAFT-v0.2.docx", "plangrid_mcp/photos/p.jpg",
                 "_pipeline/build/X-DRAFT-v0.1.docx", "_pipeline/build/X-DRAFT-v0.1-Cover.docx", "_pipeline/build/X-Review-old.xlsx"):
    assert bad_name not in names, f"{bad_name} should not be packaged"
assert "not packaged:" in r.stdout, r.stdout
assert sorted(os.listdir(dest)) == ["X-DRAFT-v0.2-Cover.docx", "X-DRAFT-v0.2.docx", "X-DRAFT-v0.2.zip", "X-Review.xlsx", "client-profile.json"], os.listdir(dest)
# second delivery: nothing overwritten, everything suffixed together
r = subprocess.run([sys.executable, "package.py", ws, dest], capture_output=True, text=True)
assert r.returncode == 0 and "'-2' suffix" in r.stdout, r.stdout + r.stderr
assert {"X-DRAFT-v0.2-2.zip", "X-DRAFT-v0.2-2.docx", "X-DRAFT-v0.2-2-Cover.docx", "X-Review-2.xlsx"} <= set(os.listdir(dest)), os.listdir(dest)
# --replace: same names overwritten in place, no third set
open(new, "wb").write(b"newer body")
r = subprocess.run([sys.executable, "package.py", ws, dest, "--replace"], capture_output=True, text=True)
assert r.returncode == 0 and "(replaced)" in r.stdout and "-3" not in r.stdout, r.stdout + r.stderr
assert open(os.path.join(dest, "X-DRAFT-v0.2.docx"), "rb").read() == b"newer body"
assert not any(n.startswith("X-DRAFT-v0.2-3") for n in os.listdir(dest)), os.listdir(dest)
PYCHECK

# MCP route: a get_tasks packet as pull_mcp.sh fetches it (photos and sheets inline, native
# types) must flow through fetch_photos -> adapt_mcp_pull -> consolidate with
# titles and photos intact, and list_sheets must fill a title a row lacks.
"$PY" - <<'PYCHECK' 2>&1 && ok "MCP route: get_tasks shape -> fetch -> adapt -> consolidate" \
    || bad "MCP route behavioural check failed"
import json, os, subprocess, sys, tempfile
d = tempfile.mkdtemp(); mcp = os.path.join(d, "plangrid_mcp"); os.makedirs(os.path.join(mcp, "photos"))
uid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
row = lambda n, sheet, photos: {"number": n, "uid": f"t{n}", "title": "V", "status": "open", "room": "", "published": True,
    "sheet_uid": sheet["uid"], "stamp": "4", "photos_count": len(photos), "comments_count": 0,
    "created_by": "e@x", "created_at": "2026-09-03T19:20:23", "updated_at": "2026-09-10T13:06:58", "deleted": False,
    "pin_deleted": False, "description": "d", "sheet": sheet, "photos": photos}
json.dump({"coverage": {}, "tasks": [
    row(41, {"uid": "s1", "name": "TO2-01B2", "description": "FLOOR PLAN B2"},
        [{"uid": uid, "title": "20260903_132033_photo", "source_url": "https://s3/x.jpg", "download_url": "http://127.0.0.1:9/photo/x.jpg"}]),
    row(42, {"uid": "s2", "name": "TO5-09", "description": ""}, [])]}, open(os.path.join(mcp, "tasks.json"), "w"))
json.dump({"sheets": [{"uid": "s2", "name": "TO5-09", "description": "DETAILS", "deleted": False}]}, open(os.path.join(mcp, "sheets.json"), "w"))
open(os.path.join(mcp, "photos", f"{uid}__20260903_132033_photo.jpg"), "wb").write(b"\xff\xd8\xff\xd9")
r = subprocess.run([sys.executable, "fetch_photos.py", "--pull", mcp, "--timeout", "2"], capture_output=True, text=True)
assert r.returncode == 0 and "already present" in r.stdout, r.stdout + r.stderr
assert json.load(open(os.path.join(mcp, "mcp_photo_urls.json")))["41"][0]["url"].startswith("http://127.0.0.1:9/")
pull = os.path.join(d, "plangrid_pull")
r = subprocess.run([sys.executable, "adapt_mcp_pull.py", "--pull", mcp, "--dest", pull], capture_output=True, text=True)
assert r.returncode == 0 and "all 2 sheets titled" in r.stdout, r.stdout + r.stderr
sheets = {s["name"]: s["description"] for s in json.load(open(os.path.join(pull, "sheets.json")))}
assert sheets == {"TO2-01B2": "FLOOR PLAN B2", "TO5-09": "DETAILS"}, sheets
r = subprocess.run([sys.executable, "consolidate.py", pull, "-o", os.path.join(d, "items.json")], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
items = {i["number"]: i for i in json.load(open(os.path.join(d, "items.json")))}
assert items[41]["sheet_description"] == "FLOOR PLAN B2" and items[42]["sheet_description"] == "DETAILS"
assert items[41]["photos"][0]["uid"] == uid
PYCHECK

# pull_mcp.sh: fetches a packet by url, proves it by sha256, refuses a bad sha
# and reports a 404 as an expired packet. Served from a throwaway local server.
# (SMOKE_BASH: the bash running this test, in a form the host python can exec;
#  on a Windows dev box a bare "bash" from python resolves to WSL's.)
SMOKE_BASH="$(cygpath -w "$BASH" 2>/dev/null || echo "$BASH")" "$PY" - <<'PYCHECK' 2>&1 && ok "pull_mcp.sh: fetch, sha check, mismatch refused, 404 reported" \
    || bad "pull_mcp.sh behavioural check failed"
import hashlib, http.server, json, os, socketserver, subprocess, sys, tempfile, threading
d = tempfile.mkdtemp(); job = os.path.join(d, "files", "0123456789abcdef0123456789abcdef"); os.makedirs(job)
tasks = json.dumps({"coverage": {}, "tasks": [{"number": 1, "photos": [{"uid": "a", "download_url": "http://x/photo/a.jpg"}]}]}).encode()
open(os.path.join(job, "tasks.json"), "wb").write(tasks)
sheets = json.dumps({"sheets": [{"name": "T1", "description": "PLAN"}]}).encode()
open(os.path.join(job, "sheets.json"), "wb").write(sheets)
class Q(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=d, **k)
    def log_message(self, *a): pass
socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 0), Q); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{port}/files/0123456789abcdef0123456789abcdef"
dest = os.path.join(d, "mcp")
def run(*specs):
    r = subprocess.run([os.environ.get("SMOKE_BASH") or "bash", "pull_mcp.sh", "--dest", dest, *specs], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr
rc, out = run(f"{base}/tasks.json#{hashlib.sha256(tasks).hexdigest()}", f"{base}/sheets.json#{hashlib.sha256(sheets).hexdigest()}")
assert rc == 0 and "1 tasks, 1 photos (1 with download_url)" in out and "1 sheets, 1 titled" in out and out.count("sha ok") == 2, out
assert open(os.path.join(dest, "tasks.json"), "rb").read() == tasks
rc, out = run(f"{base}/tasks.json#" + "0" * 64)
assert rc != 0 and "SHA256 MISMATCH" in out and not os.path.exists(os.path.join(dest, "tasks.json")), out
rc, out = run(f"{base}/photos.json")
assert rc != 0 and "HTTP 404" in out and "expired" in out, out
assert "Permission denied" not in out, out
# a stale, unwritable /tmp/pull_mcp.err from another session must not matter
import re as _re
assert not _re.search(r"2>\s*/tmp/\w", open("pull_mcp.sh", encoding="utf-8").read()), "fixed /tmp redirect is back"
srv.shutdown()
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
