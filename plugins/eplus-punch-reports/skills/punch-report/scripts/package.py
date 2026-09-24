#!/usr/bin/env python3
"""
package.py -- bundle a finished punch report workspace and deliver it.

The pipeline never works inside the user's selected project folder. It runs in
the session's own workspace, and the ONLY write to the project folder is the
single delivery this script performs at the end: one zip holding the workspace
(pipeline, sources, data, build, handoff) plus the rendered .docx, its cover,
and the review .xlsx placed beside it so the reviewer does not have to unzip
anything to start reading.

    python3 scripts/package.py <workspace> <destination> [--name <stem>] [--dry-run]
                               [--replace] [--pdf]

<workspace>    the folder that holds _pipeline/ and the report inputs
<destination>  the user's selected project folder (or any folder to deliver to)
--name         zip stem; defaults to the rendered .docx stem, or the workspace
               folder name if no .docx has been rendered
--dry-run      list what would be packaged and delivered, write nothing
--replace      overwrite an earlier delivery that has the SAME stem instead of
               suffixing the new one -2, -3, ... Only when the user has said
               the earlier copy should be replaced; the default never touches
               an existing file.
--pdf          also place the newest .pdf from _pipeline/build/ beside the zip
               (only when the user asked for a PDF; it is a convenience copy)

Where the deliverables are found: the newest body .docx under _pipeline/build/
(the renderer writes there), its -Cover.docx when one exists, and the newest
.xlsx under _pipeline/build/ (review_sheet.py writes there; _pipeline/ and the
workspace root are accepted for older layouts).

What the zip holds, and what it does not. The package is the reviewer's copy
of the workspace and the next run's starting point, so it carries the inputs,
the data, the build the renderer read, the docs and the scripts, and nothing
that was superseded during the run. Field result 2026-09-14: a 26.6 MB, 252
file package carried the same 13 photos twice, a template stamped into the
wrong place, a whole build/v0.2/ duplicate tree, the previous version's docx,
and worker probe files. Excluded now, and each exclusion is printed:

  - node_modules/, __pycache__/, _scratch/, .DS_Store, Thumbs.db, ~$ lock files
  - *.bak.json (review_sheet.py's backups)
  - any file or folder whose name starts with "_", except _pipeline itself
    (worker scratch such as _write_probe.py; scratch belongs in _scratch/)
  - _pipeline/template/ and _pipeline/templates/ (a template stamped into the
    wrong place; the real template files live at the workspace root)
  - subfolders of _pipeline/build/ other than assets/, thumbs_uniform/ and
    sheet_clips_jpg/ (a build/v0.2/ style duplicate tree)
  - plangrid_mcp/photos/ and plangrid_mcp/pdf_photos/ when plangrid_pull/photos/
    exists (adapt_mcp_pull.py already copied them; the MCP json stays)
  - every .docx and .xlsx except the three delivered (earlier renders are
    reproducible from the data and clutter the reviewer's view)

Re-delivery: a render under a NEW output_filename (v0.1 -> v0.2) has a new
stem and never collides. Earlier versions of the same report already in the
destination (their body, cover, review sheet and package) are written INTO the
new package under previous-versions/ and then removed from the folder, so the
folder shows the current version and the inputs (the Task Report PDF,
client-profile.json) only; field result 2026-09-23: a v0.2 delivery left ten
files. A file is removed only after the new zip is verified to hold an
identical copy (size and CRC). Cowork allows deletes in a connected folder only
after the user grants it once per folder; until then the script prints
CLEANUP PENDING with the files and the follow-up command,
`package.py --prune <destination>`, which removes exactly the files the newest
package holds a verified copy of. --keep-previous leaves earlier versions where
they are. If the stem itself is taken, every delivered file gets the next free
"-2", "-3", ... suffix; with --replace, files of the same stem are overwritten
in place instead.

Exit status is non-zero if the workspace has no _pipeline/, if the destination
is missing, if no rendered .docx exists, or if the zip written does not contain
every file that was counted.
"""
import argparse
import os
import re
import shutil
import sys
import zipfile

# Paperwork a person has to write before the package leaves. Each entry is a
# file (relative to the workspace) and the template text that proves it was
# never touched. Field result 2026-09-14: a package shipped with the scope
# decision, the precedent pass and the README scope paragraph still reading
# as the template. --allow-placeholders overrides, for a dry run or a test.
REQUIRED_PAPERWORK = [
    ("_pipeline/PROCESS-LOG.md", "<What was included, what was excluded"),
    ("_pipeline/PROCESS-LOG.md", "- Tools used and roughly how many calls"),
    ("_pipeline/ISSUES-LIST.md", "### Item <N> (PlanGrid #<N>)"),
    ("README.md", "<What this report covers, what was excluded"),
    ("_pipeline/CLAUDE.md", "<State what was excluded and by whose direction"),
]

EXCLUDE_DIRS = {"node_modules", "__pycache__", "_scratch"}
EXCLUDE_SUFFIXES = (".bak.json",)
EXCLUDE_NAMES = {".DS_Store", "Thumbs.db"}
BUILD_KEEP_DIRS = {"assets", "thumbs_uniform", "sheet_clips_jpg"}
STRAY_PIPELINE_DIRS = {"template", "templates"}


def newest(paths):
    paths = [p for p in paths if os.path.isfile(p)]
    return max(paths, key=os.path.getmtime) if paths else None


def find_deliverables(ws):
    """Newest body .docx and .xlsx the pipeline produced, wherever it put them."""
    build = os.path.join(ws, "_pipeline", "build")
    pipe = os.path.join(ws, "_pipeline")
    docx, xlsx = [], []
    for d in (build, pipe, ws):
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.startswith("~$"):
                continue
            p = os.path.join(d, f)
            if f.lower().endswith("-cover.docx"):
                continue  # the cover is paired with its body below, never the deliverable itself
            if f.lower().endswith(".docx"):
                docx.append(p)
            elif f.lower().endswith(".xlsx"):
                xlsx.append(p)
    return newest(docx), newest(xlsx)


def collect(ws, keep_files):
    """(files to zip, [(reason, relpath), ...] excluded). keep_files are the
    delivered .docx/.xlsx, kept even though every other office file is not."""
    files, skipped = [], []
    build = os.path.join(ws, "_pipeline", "build")
    pipe = os.path.join(ws, "_pipeline")
    live_photos = os.path.isdir(os.path.join(ws, "plangrid_pull", "photos"))
    keep_abs = {os.path.abspath(p) for p in keep_files if p}

    def rel(p):
        return os.path.relpath(p, ws).replace(os.sep, "/")

    for dirpath, dirnames, filenames in os.walk(ws):
        pruned = []
        for d in list(dirnames):
            full = os.path.join(dirpath, d)
            reason = None
            if d in EXCLUDE_DIRS:
                reason = "cache or scratch"
            elif d.startswith("_") and full != pipe:
                reason = "name starts with _ (worker scratch)"
            elif dirpath == pipe and d in STRAY_PIPELINE_DIRS:
                reason = "template stamped into the wrong place"
            elif dirpath == build and d not in BUILD_KEEP_DIRS:
                reason = "extra build subfolder (duplicate render tree)"
            elif live_photos and os.path.basename(dirpath) == "plangrid_mcp" \
                    and os.path.dirname(dirpath) == ws and d in ("photos", "pdf_photos"):
                reason = "raw photos already copied to plangrid_pull/photos"
            if reason:
                pruned.append(d)
                skipped.append((reason, rel(full) + "/"))
        dirnames[:] = [d for d in dirnames if d not in pruned]

        for f in filenames:
            full = os.path.join(dirpath, f)
            low = f.lower()
            reason = None
            if f in EXCLUDE_NAMES or f.startswith("~$"):
                reason = "editor lock or OS file"
            elif f.endswith(EXCLUDE_SUFFIXES):
                reason = "review sheet backup"
            elif f.startswith("_"):
                reason = "name starts with _ (worker scratch)"
            elif low.endswith((".docx", ".xlsx")) and os.path.abspath(full) not in keep_abs:
                reason = "earlier render, not the delivered file"
            if reason:
                skipped.append((reason, rel(full)))
            else:
                files.append(full)
    return files, skipped


def unfilled_paperwork(ws):
    """(file, placeholder) pairs whose template text is still present."""
    hits = []
    for rel, marker in REQUIRED_PAPERWORK:
        p = os.path.join(ws, rel)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                if marker in f.read():
                    hits.append((rel, marker))
        except OSError:
            pass
    return hits


def free_suffix(dest, stem, names):
    """Smallest suffix such that none of <stem><suffix><ext> already exist in dest."""
    n = 1
    while True:
        suffix = "" if n == 1 else f"-{n}"
        if not any(os.path.exists(os.path.join(dest, f"{stem}{suffix}{ext}")) for ext in names):
            return suffix
        n += 1


PREV = "previous-versions/"
DRAFT_STEM_RE = re.compile(r"^(?P<base>.+?)-DRAFT-v(?P<a>\d+)\.(?P<b>\d+)$", re.I)


def superseded(dest, stem, keep_names):
    """Earlier deliveries of the same report in dest: every version up to this one.

    Field result 2026-09-23: after a v0.2 delivery the project folder held ten
    files, v0.1's body, cover, review sheet and package beside v0.2's. The
    reviewer should see the current version and the inputs; earlier versions
    travel inside the new package under previous-versions/.
    """
    m = DRAFT_STEM_RE.match(stem)
    if not m or not os.path.isdir(dest):
        return []
    base, cur = m.group("base"), (int(m.group("a")), int(m.group("b")))
    b = re.escape(base)
    versioned = re.compile(rf"^{b}-DRAFT-v(\d+)\.(\d+)(?:-\d+)?(?:-Cover|-Review)?\.(?:docx|zip|xlsx)$", re.I)
    sheet = re.compile(rf"^{b}-Review(?:-\d+)?\.xlsx$", re.I)
    out = []
    for f in sorted(os.listdir(dest)):
        if f in keep_names or f.startswith("~$"):
            continue
        mv = versioned.match(f)
        if mv:
            if (int(mv.group(1)), int(mv.group(2))) <= cur:
                out.append(os.path.join(dest, f))
        elif sheet.match(f):
            out.append(os.path.join(dest, f))
    return out


def crc_of(path):
    import zlib
    crc = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            crc = zlib.crc32(chunk, crc)
    return crc & 0xFFFFFFFF


def prune(dest, zip_path=None):
    """Remove files from dest that sit, byte for byte, in a package's previous-versions/.

    Nothing is removed unless the package holds an identical copy (size and CRC).
    Returns (removed, blocked) lists of file names.
    """
    if zip_path is None:
        # the package with the highest version; a same-version re-delivery (-2) wins by mtime
        best = None
        for f in os.listdir(dest):
            m = re.search(r"-DRAFT-v(\d+)\.(\d+)(?:-\d+)?\.zip$", f, re.I)
            if m:
                p = os.path.join(dest, f)
                key = (int(m.group(1)), int(m.group(2)), os.path.getmtime(p))
                if best is None or key > best[0]:
                    best = (key, p)
        zip_path = best[1] if best else None
    if not zip_path:
        return [], []
    removed, blocked = [], []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if not info.filename.startswith(PREV) or info.filename.endswith("/"):
                continue
            name = info.filename[len(PREV):]
            p = os.path.join(dest, name)
            if "/" in name or not os.path.isfile(p):
                continue
            if os.path.getsize(p) != info.file_size or crc_of(p) != info.CRC:
                continue
            try:
                os.remove(p)
                removed.append(name)
            except OSError:
                blocked.append(name)
    return removed, blocked


def report_cleanup(dest, zip_path, removed, blocked):
    zname = os.path.basename(zip_path)
    for n in removed:
        print(f"moved       : {n} -> {zname}:{PREV}{n}")
    if blocked:
        folder = os.path.basename(os.path.normpath(dest))
        print(f"CLEANUP PENDING: {len(blocked)} earlier file(s) are safely inside {zname} under {PREV} "
              f"but this folder does not allow deletes yet: {', '.join(blocked)}")
        # The permission prompt Cowork shows names one file and says nothing about
        # why. Field result 2026-09-23: the model asked with "I'll tidy them out of
        # the folder", and a user could not tell what was about to be deleted. So
        # the exact message is written here and posted BEFORE the permission call.
        print("  STEP 1. Post this message to the user, as written, before asking for permission:")
        print("  ----")
        print(f"  Cowork is about to ask you to allow file deletion in the \"{folder}\" folder. Here is exactly "
              f"what I will delete, and why:")
        for n in blocked:
            print(f"  - {n}")
        print(f"  These are the previous version of the report. Identical copies are already saved inside "
              f"{zname}, in its {PREV} folder, so nothing is lost. I delete only these {len(blocked)} file(s); "
              f"nothing else in the folder is touched (your Task Report and client-profile.json stay). "
              f"If you decline, they simply stay in the folder.")
        print("  ----")
        print("  STEP 2. Ask for delete permission once (Cowork: allow_cowork_file_delete with the path of "
              f"{os.path.join(dest, blocked[0])}).")
        print("  STEP 3. If it was allowed, run:")
        print(f"  python3 scripts/package.py --prune \"{dest}\"")


def deliver_template(docx, dest, args):
    """An empty fill-in report: the body and its cover, nothing else. There is no
    data worth a package, and the user asked for the two Word files only. Never
    overwrites: an existing name gets the next free -2, -3, ... suffix."""
    stem = args.name or os.path.splitext(os.path.basename(docx))[0]
    cover = re.sub(r"\.docx$", "-Cover.docx", docx, flags=re.I)
    pairs = [(docx, ".docx")] + ([(cover, "-Cover.docx")] if os.path.isfile(cover) else [])
    suffix = free_suffix(dest, stem, [".docx"])
    print(f"destination : {dest}  (template only: body and cover, no package)")
    for src, tail in pairs:
        name = f"{stem}{suffix}{tail}"
        if args.dry_run:
            print(f"would deliver: {name}")
            continue
        shutil.copy2(src, os.path.join(dest, name))
        print(f"delivered   : {name}")
    return 0


def main():
    if "--prune" in sys.argv:
        ap = argparse.ArgumentParser(description="remove earlier versions already inside the newest package")
        ap.add_argument("--prune", required=True, metavar="DESTINATION")
        a = ap.parse_args()
        dest = os.path.abspath(a.prune)
        removed, blocked = prune(dest)
        for n in removed:
            print(f"removed     : {n} (a copy is inside the newest package, {PREV})")
        if blocked:
            print(f"ERROR: still not allowed to delete in {dest}: {', '.join(blocked)}")
            return 1
        if not removed:
            print("nothing to prune: no earlier version in this folder matches a copy inside the newest package")
        return 0

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("workspace")
    ap.add_argument("destination")
    ap.add_argument("--keep-previous", action="store_true",
                    help="leave earlier versions beside the new delivery instead of moving them into "
                         "its package under previous-versions/")
    ap.add_argument("--name", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--replace", action="store_true",
                    help="overwrite an earlier delivery with the same stem instead of suffixing "
                         "(only when the user has asked for the earlier copy to be replaced)")
    ap.add_argument("--pdf", action="store_true",
                    help="also place the newest .pdf from _pipeline/build/ beside the zip "
                         "(only when the user asked for a PDF; it is a convenience copy)")
    ap.add_argument("--allow-placeholders", action="store_true",
                    help="deliver even though PROCESS-LOG, ISSUES-LIST, README or CLAUDE.md still "
                         "carry template text (tests and dry runs only)")
    ap.add_argument("--template-only", action="store_true",
                    help="an empty fill-in report (blank_template.py): deliver the body and the cover "
                         "only; no package, no review sheet, no client profile, no paperwork check")
    args = ap.parse_args()

    ws = os.path.abspath(args.workspace)
    dest = os.path.abspath(args.destination)
    if not os.path.isdir(os.path.join(ws, "_pipeline")):
        sys.exit(f"ERROR: {ws} has no _pipeline/ folder; is this the workspace?")
    if not os.path.isdir(dest):
        sys.exit(f"ERROR: destination {dest} does not exist")

    docx, xlsx = find_deliverables(ws)
    if not docx:
        sys.exit("ERROR: no rendered .docx under _pipeline/build/; render before delivering")
    if args.template_only:
        return deliver_template(docx, dest, args)
    unfilled = unfilled_paperwork(ws)
    if unfilled and not (args.allow_placeholders or args.dry_run):
        lines = "\n".join(f"  {rel}: still contains {marker!r}" for rel, marker in unfilled)
        sys.exit("ERROR: the paperwork still carries template text; write these sections before delivering "
                 "(scope decision, precedent pass, issues, README scope):\n" + lines +
                 "\n--allow-placeholders overrides for tests and dry runs.")
    if unfilled:
        for rel, marker in unfilled:
            print(f"WARNING     : {rel} still contains {marker!r}")
    stem = args.name or os.path.splitext(os.path.basename(docx))[0]
    # The cover is a separate file when cover_mode is "template"; deliver it
    # beside the body under the same suffix so the two stay paired.
    cover = re.sub(r"\.docx$", "-Cover.docx", docx, flags=re.I)
    cover = cover if os.path.isfile(cover) else None

    files, skipped = collect(ws, [docx, cover, xlsx])
    total = sum(os.path.getsize(f) for f in files)

    # One suffix for the whole delivery, so the zip, the .docx and the .xlsx
    # always share a name and never collide with an earlier delivery.
    exts = [".zip", ".docx"] + ([".xlsx"] if xlsx else [])
    suffix = "" if args.replace else free_suffix(dest, stem, exts)
    zip_path = os.path.join(dest, f"{stem}{suffix}.zip")
    beside = [(docx, f"{stem}{suffix}.docx")]
    if cover:
        beside.append((cover, f"{stem}{suffix}-Cover.docx"))
    if xlsx:
        xstem = os.path.splitext(os.path.basename(xlsx))[0]
        xname = f"{xstem}{suffix}.xlsx"
        # The review sheet's name carries no version (<report>-Review.xlsx), so a
        # v0.2 delivery found v0.1's sheet there and left it stale (field result
        # 2026-09-23). A later version's sheet takes the body's versioned stem.
        if not args.replace and os.path.exists(os.path.join(dest, xname)):
            xname = f"{stem}{suffix}-Review.xlsx"
        beside.append((xlsx, xname))
    pdf = None
    if args.pdf:
        build = os.path.join(ws, "_pipeline", "build")
        pdf = newest([os.path.join(build, f) for f in os.listdir(build)
                      if f.lower().endswith(".pdf")]) if os.path.isdir(build) else None
        if pdf:
            pstem = os.path.splitext(os.path.basename(pdf))[0]
            beside.append((pdf, f"{pstem}{suffix}.pdf"))
        else:
            print("WARNING: --pdf given but no .pdf in _pipeline/build/; run scripts/export_pdf.py first")

    print(f"workspace   : {ws}")
    print(f"destination : {dest}")
    print(f"package     : {os.path.basename(zip_path)}  ({len(files)} files, {total / 1048576:.1f} MB)")
    print(f"report      : {os.path.relpath(docx, ws)} -> {beside[0][1]}")
    if cover:
        print(f"cover       : {os.path.relpath(cover, ws)} -> {stem}{suffix}-Cover.docx  (separate file; body page 1 is blank for it)")
    if xlsx:
        xname = next(n for s, n in beside if s == xlsx)
        print(f"review sheet: {os.path.relpath(xlsx, ws)} -> {xname}")
    else:
        print("review sheet: (none found; review_sheet.py export not run)")
    if pdf:
        print(f"pdf         : {os.path.relpath(pdf, ws)} -> {beside[-1][1]}  (convenience copy, LibreOffice pagination)")
    if skipped:
        by_reason = {}
        for reason, p in skipped:
            by_reason.setdefault(reason, []).append(p)
        for reason, paths in by_reason.items():
            shown = ", ".join(paths[:4]) + (f", +{len(paths) - 4} more" if len(paths) > 4 else "")
            print(f"not packaged: {len(paths)} ({reason}): {shown}")
    if suffix:
        print(f"note        : an earlier delivery exists; this one carries the '{suffix}' suffix. Nothing was removed.")
    if args.replace:
        existing = [n for _, n in beside if os.path.exists(os.path.join(dest, n))]
        if os.path.exists(zip_path):
            existing.append(os.path.basename(zip_path))
        if existing:
            print(f"note        : --replace overwrites {len(existing)} earlier file(s): {', '.join(existing)}")
    # Earlier versions of this report in the destination go INTO the new package
    # (previous-versions/<file>) and leave the folder, so the folder shows the
    # current version and the inputs only. They are removed only once the new zip
    # is verified to hold an identical copy of each.
    keep_names = {n for _, n in beside} | {os.path.basename(zip_path), "client-profile.json"}
    old = [] if args.keep_previous else superseded(dest, stem, keep_names)
    if old:
        print(f"earlier     : {len(old)} file(s) of earlier versions go inside the new package under {PREV}: "
              + ", ".join(os.path.basename(p) for p in old))
    if args.dry_run:
        for f in files:
            print("  ", os.path.relpath(f, ws))
        return 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, os.path.relpath(f, ws))
        for p in old:
            zf.write(p, PREV + os.path.basename(p))
    with zipfile.ZipFile(zip_path) as zf:
        n = len(zf.namelist())
        if n != len(files) + len(old):
            sys.exit(f"ERROR: zip holds {n} entries but {len(files) + len(old)} were counted; "
                     f"delivery at {zip_path} is incomplete, deliver again under a new --name")

    for src, name in beside:
        target = os.path.join(dest, name)
        existed = os.path.exists(target)
        if existed and not args.replace:
            print(f"WARNING: {name} already exists in the destination; left as is, the copy inside the zip is current")
            continue
        shutil.copy2(src, target)
        print(f"delivered   : {name}" + ("  (replaced)" if existed else ""))
    print(f"delivered   : {os.path.basename(zip_path)}")

    # The client profile is the one file that is updated in place: it holds the
    # client-level facts supplied by the user (name, address, EP number, inspector,
    # reviewer, drop phrases, cover settings) so the next report for this client
    # starts from them instead of asking again or reading memory.
    profile = os.path.join(ws, "client-profile.json")
    if os.path.isfile(profile):
        shutil.copy2(profile, os.path.join(dest, "client-profile.json"))
        print("delivered   : client-profile.json (updated in place)")
    if old:
        removed, blocked = prune(dest, zip_path)
        report_cleanup(dest, zip_path, removed, blocked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
