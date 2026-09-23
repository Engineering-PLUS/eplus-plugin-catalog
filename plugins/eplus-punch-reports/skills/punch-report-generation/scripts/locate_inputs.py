#!/usr/bin/env python3
"""
locate_inputs.py -- find the project folder and the report inputs without asking.

Run FIRST in a punch report run, from the plugin (no workspace exists yet):

    python3 <plugin skill>/scripts/locate_inputs.py [<hint>] [--mnt <dir>] [--json]

<hint> is whatever the user typed after /punch-report ("ctx2", "Miner Ops"),
matched loosely against the names of the folders connected to this Cowork
session. Nothing here opens the folder picker or asks a question: field result
2026-09-23, the model opened the picker with no explanation because the
argument named a folder that was not connected, and the user cancelled it.

What it reports:
  project folder   the connected folder to read inputs from and deliver to:
                   the one whose name matches <hint>, else the only one
                   connected. None when nothing (or more than one, with no
                   hint that picks one) is connected. With none, the run
                   builds and delivers into the session outputs folder and
                   the final message says the report is not in a project
                   folder yet.
  inputs           per connected folder and uploads/: PlanGrid pull folders
                   (a tasks.json), Task Report PDFs, client-profile.json,
                   earlier delivered packages (*Punch-Report*.zip) and the
                   highest -DRAFT-vN.N already delivered there.
  next version     the version the new render must carry, from the project
                   folder's own deliveries (never from memory).

Connected folders are the entries of /sessions/<session>/mnt/ other than
outputs/, uploads/ and dot-folders (.local-plugins, ...). Stdlib only.
"""
import argparse
import glob
import json
import os
import re
import sys

SKIP = {"outputs", "uploads"}
VERSION_RE = re.compile(r"-DRAFT-v(\d+)\.(\d+)", re.I)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def find_mnt(explicit):
    if explicit:
        return explicit if os.path.isdir(explicit) else None
    cands = sorted(glob.glob("/sessions/*/mnt"))
    with_outputs = [c for c in cands if os.path.isdir(os.path.join(c, "outputs"))]
    return (with_outputs or cands or [None])[0]


def scan(folder, depth=3):
    """Inputs found under one folder, a few levels deep (shares are slow)."""
    found = {"pulls": [], "task_reports": [], "profile": None, "packages": [], "drafts": []}
    base = folder.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(folder):
        if dirpath.count(os.sep) - base >= depth:
            dirnames[:] = []
        # a workspace or raw MCP material is not an input pull
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "_")) and d not in
                       ("node_modules", "plangrid_mcp", "__pycache__")]
        low = {f.lower(): f for f in filenames}
        if "tasks.json" in low and "delta_" not in os.path.basename(dirpath):
            found["pulls"].append(dirpath)
        for f in filenames:
            fl = f.lower()
            p = os.path.join(dirpath, f)
            if fl.endswith(".pdf") and "task report" in fl.replace("_", " "):
                found["task_reports"].append(p)
            elif fl == "client-profile.json" and found["profile"] is None:
                found["profile"] = p
            elif fl.endswith(".zip") and "punch-report" in fl:
                found["packages"].append(p)
            elif fl.endswith(".docx") and VERSION_RE.search(f) and not fl.startswith("~$") \
                    and not fl.endswith("-cover.docx"):
                found["drafts"].append(p)
    for k in ("task_reports", "packages", "drafts"):
        found[k].sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return found


def highest_version(paths):
    best = None
    for p in paths:
        m = VERSION_RE.search(os.path.basename(p))
        if m:
            v = (int(m.group(1)), int(m.group(2)))
            best = v if best is None or v > best else best
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("hint", nargs="?", default="")
    ap.add_argument("--mnt", default=None, help="the session mount folder (default /sessions/*/mnt)")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    args = ap.parse_args()

    mnt = find_mnt(args.mnt)
    if not mnt:
        sys.exit("ERROR: no /sessions/*/mnt folder found; pass --mnt")
    outputs = os.path.join(mnt, "outputs")
    uploads = os.path.join(mnt, "uploads")
    connected = sorted(os.path.join(mnt, d) for d in os.listdir(mnt)
                       if os.path.isdir(os.path.join(mnt, d)) and not d.startswith(".") and d not in SKIP)

    hint = norm(args.hint)
    matches = [c for c in connected if hint and (hint in norm(os.path.basename(c)) or norm(os.path.basename(c)) in hint)]
    if len(matches) == 1:
        project, why = matches[0], f"its name matches '{args.hint}'"
    elif not hint and len(connected) == 1:
        project, why = connected[0], "it is the only folder connected to this session"
    elif hint and not matches and len(connected) == 1:
        project, why = connected[0], (f"it is the only folder connected; its name does not match "
                                      f"'{args.hint}', so confirm it in the final message")
    else:
        project = None
        if not connected:
            why = "no folder is connected to this session"
        elif len(matches) > 1:
            why = f"{len(matches)} connected folders match '{args.hint}'"
        else:
            why = f"{len(connected)} folders are connected and none is picked by '{args.hint}'"

    scans = {c: scan(c) for c in connected}
    if os.path.isdir(uploads):
        scans[uploads] = scan(uploads, depth=2)
    v = highest_version(scans[project]["drafts"] + scans[project]["packages"]) if project else None
    next_version = f"{v[0]}.{v[1] + 1}" if v else "0.1"

    result = {
        "mnt": mnt, "outputs": outputs, "connected": connected, "hint": args.hint,
        "project_folder": project, "project_folder_reason": why,
        "deliver_to": project or outputs,
        "next_version": next_version,
        "latest_package": (scans[project]["packages"][0] if project and scans[project]["packages"] else None),
        "inputs": scans,
    }
    if args.json:
        print(json.dumps(result, indent=1))
        return 0

    print(f"session mount  : {mnt}")
    print(f"connected      : {', '.join(os.path.basename(c) for c in connected) or 'none'}")
    if project:
        print(f"project folder : {project}  ({why})")
    else:
        print(f"project folder : NONE ({why}).")
        print(f"                 Build and deliver into {outputs}; say so plainly in the final")
        print("                 message and ask for the folder there, never before the build.")
    print(f"deliver to     : {result['deliver_to']}")
    print(f"next version   : v{next_version}" + (f"  (highest delivered there: v{v[0]}.{v[1]})" if v else "  (nothing delivered there yet)"))
    if result["latest_package"]:
        print(f"prior package  : {result['latest_package']}  (a re-run starts from it: init_workspace.sh --from-package)")
    for folder, f in scans.items():
        label = os.path.basename(folder)
        bits = []
        if f["pulls"]:
            bits.append("pull " + ", ".join(f["pulls"][:3]))
        if f["task_reports"]:
            bits.append("Task Report " + ", ".join(f["task_reports"][:2]))
        if f["profile"]:
            bits.append("profile " + f["profile"])
        if f["packages"]:
            bits.append(f"{len(f['packages'])} package(s)")
        print(f"  {label:<14}: " + ("; ".join(bits) if bits else "no report inputs found"))
    if not any(f["pulls"] for f in scans.values()):
        print("pull           : none on disk; pull from the plangrid MCP (reference/build-data.md, Step 0b)")
    if not any(f["task_reports"] for f in scans.values()):
        print("task report    : none; build without pin clips and list it in the finish list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
