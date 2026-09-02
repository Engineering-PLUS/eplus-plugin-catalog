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

Excluded from the zip: node_modules/, __pycache__/, *.bak.json, .DS_Store.
Everything else ships, sources included, so the delivered document and the
files that generate it can never disagree.

Exit status is non-zero if the workspace has no _pipeline/, if the destination
is missing, or if the zip written does not contain every file that was counted.
"""
import argparse
import os
import shutil
import sys
import zipfile

EXCLUDE_DIRS = {"node_modules", "__pycache__"}
EXCLUDE_SUFFIXES = (".bak.json",)
EXCLUDE_NAMES = {".DS_Store", "Thumbs.db"}


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            if f in EXCLUDE_NAMES or f.endswith(EXCLUDE_SUFFIXES):
                continue
            yield os.path.join(dirpath, f)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("workspace")
    ap.add_argument("destination")
    ap.add_argument("--name", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ws = os.path.abspath(args.workspace)
    dest = os.path.abspath(args.destination)
    if not os.path.isdir(os.path.join(ws, "_pipeline")):
        sys.exit(f"ERROR: {ws} has no _pipeline/ folder; is this the workspace?")
    if not os.path.isdir(dest):
        sys.exit(f"ERROR: destination {dest} does not exist")

    top_level = sorted(os.listdir(ws))
    docx = [f for f in top_level if f.lower().endswith(".docx") and not f.startswith("~$")]
    xlsx = [f for f in top_level if f.lower().endswith(".xlsx") and not f.startswith("~$")]
    stem = args.name or (os.path.splitext(docx[0])[0] if docx else os.path.basename(ws))
    zip_path = os.path.join(dest, stem + ".zip")

    files = list(iter_files(ws))
    total = sum(os.path.getsize(f) for f in files)
    print(f"workspace   : {ws}")
    print(f"destination : {dest}")
    print(f"package     : {os.path.basename(zip_path)}  ({len(files)} files, {total / 1048576:.1f} MB)")
    print(f"beside it   : {', '.join(docx + xlsx) or '(no .docx/.xlsx at workspace root yet)'}")
    if not docx:
        print("WARNING: no rendered .docx at the workspace root; delivering the pipeline without a report.")
    if args.dry_run:
        for f in files:
            print("  ", os.path.relpath(f, ws))
        return 0

    if os.path.exists(zip_path):
        sys.exit(f"ERROR: {zip_path} already exists; pick another --name rather than overwrite a delivery")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, os.path.relpath(f, ws))
    with zipfile.ZipFile(zip_path) as zf:
        n = len(zf.namelist())
        if n != len(files):
            os.remove(zip_path)
            sys.exit(f"ERROR: zip holds {n} entries but {len(files)} were counted; delivery removed")

    for f in docx + xlsx:
        target = os.path.join(dest, f)
        if os.path.exists(target):
            print(f"WARNING: {f} already exists in the destination; leaving it, the copy inside the zip is current")
            continue
        shutil.copy2(os.path.join(ws, f), target)
        print(f"delivered   : {f}")
    print(f"delivered   : {os.path.basename(zip_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
