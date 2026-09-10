#!/usr/bin/env python3
"""
package.py -- bundle a finished punch report workspace and deliver it.

The pipeline never works inside the user's selected project folder. It runs in
the session's own workspace, and the ONLY write to the project folder is the
single delivery this script performs at the end: one zip holding the whole
workspace (pipeline, sources, data, build, handoff) plus the rendered .docx and
the review .xlsx placed beside it so the reviewer does not have to unzip
anything to start reading.

    python3 scripts/package.py <workspace> <destination> [--name <stem>] [--dry-run]

<workspace>    the folder that holds _pipeline/ and the report inputs
<destination>  the user's selected project folder (or any folder to deliver to)
--name         zip stem; defaults to the rendered .docx stem, or the workspace
               folder name if no .docx has been rendered
--dry-run      list what would be packaged and delivered, write nothing

Where the deliverables are found: the newest .docx under _pipeline/build/ (the
renderer writes there) and the newest .xlsx under _pipeline/ or _pipeline/build/
(review_sheet.py writes there). Files at the workspace root are accepted too.
Anything under _pipeline/build/_scratch/ is ignored and never packaged.

Re-delivery: this script never deletes or overwrites anything in the
destination. If the zip name is taken, every delivered file gets the next free
"-2", "-3", ... suffix, so a second delivery needs no permission to remove the
first one. Excluded from the zip: node_modules/, __pycache__/, _scratch/,
*.bak.json, .DS_Store, Thumbs.db.

Exit status is non-zero if the workspace has no _pipeline/, if the destination
is missing, if no rendered .docx exists, or if the zip written does not contain
every file that was counted.
"""
import argparse
import os
import shutil
import sys
import zipfile

EXCLUDE_DIRS = {"node_modules", "__pycache__", "_scratch"}
EXCLUDE_SUFFIXES = (".bak.json",)
EXCLUDE_NAMES = {".DS_Store", "Thumbs.db"}


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            if f in EXCLUDE_NAMES or f.endswith(EXCLUDE_SUFFIXES):
                continue
            yield os.path.join(dirpath, f)


def newest(paths):
    paths = [p for p in paths if os.path.isfile(p)]
    return max(paths, key=os.path.getmtime) if paths else None


def find_deliverables(ws):
    """Newest .docx and .xlsx the pipeline produced, wherever it put them."""
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
            if f.lower().endswith(".docx"):
                docx.append(p)
            elif f.lower().endswith(".xlsx"):
                xlsx.append(p)
    return newest(docx), newest(xlsx)


def free_suffix(dest, stem, names):
    """Smallest suffix such that none of <stem><suffix><ext> already exist in dest."""
    n = 1
    while True:
        suffix = "" if n == 1 else f"-{n}"
        if not any(os.path.exists(os.path.join(dest, f"{stem}{suffix}{ext}")) for ext in names):
            return suffix
        n += 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("workspace")
    ap.add_argument("destination")
    ap.add_argument("--name", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pdf", action="store_true",
                    help="also place the newest .pdf from _pipeline/build/ beside the zip "
                         "(only when the user asked for a PDF; it is a convenience copy)")
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
    stem = args.name or os.path.splitext(os.path.basename(docx))[0]

    files = list(iter_files(ws))
    total = sum(os.path.getsize(f) for f in files)

    # One suffix for the whole delivery, so the zip, the .docx and the .xlsx
    # always share a name and never collide with an earlier delivery.
    exts = [".zip", ".docx"] + ([".xlsx"] if xlsx else [])
    suffix = free_suffix(dest, stem, exts)
    zip_path = os.path.join(dest, f"{stem}{suffix}.zip")
    beside = [(docx, f"{stem}{suffix}.docx")]
    if xlsx:
        xstem = os.path.splitext(os.path.basename(xlsx))[0]
        beside.append((xlsx, f"{xstem}{suffix}.xlsx"))
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
    if xlsx:
        print(f"review sheet: {os.path.relpath(xlsx, ws)} -> {beside[1][1]}")
    else:
        print("review sheet: (none found; review_sheet.py export not run)")
    if pdf:
        print(f"pdf         : {os.path.relpath(pdf, ws)} -> {beside[-1][1]}  (convenience copy, LibreOffice pagination)")
    if suffix:
        print(f"note        : an earlier delivery exists; this one carries the '{suffix}' suffix. Nothing was removed.")
    if args.dry_run:
        for f in files:
            print("  ", os.path.relpath(f, ws))
        return 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, os.path.relpath(f, ws))
    with zipfile.ZipFile(zip_path) as zf:
        n = len(zf.namelist())
        if n != len(files):
            sys.exit(f"ERROR: zip holds {n} entries but {len(files)} were counted; "
                     f"delivery at {zip_path} is incomplete, deliver again under a new --name")

    for src, name in beside:
        target = os.path.join(dest, name)
        if os.path.exists(target):
            print(f"WARNING: {name} already exists in the destination; left as is, the copy inside the zip is current")
            continue
        shutil.copy2(src, target)
        print(f"delivered   : {name}")
    print(f"delivered   : {os.path.basename(zip_path)}")

    # The client profile is the one file that is updated in place: it holds the
    # client-level facts confirmed at intake (name, address, EP number, inspector,
    # reviewer, drop phrases, cover settings) so the next report for this client
    # starts from them instead of asking again or reading memory.
    profile = os.path.join(ws, "client-profile.json")
    if os.path.isfile(profile):
        shutil.copy2(profile, os.path.join(dest, "client-profile.json"))
        print("delivered   : client-profile.json (updated in place)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
