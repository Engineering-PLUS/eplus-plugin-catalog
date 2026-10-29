#!/usr/bin/env python3
"""
prefill_config.py -- fill report.config.json from sources on record, with no questions.

Run from the workspace's _pipeline/ after the data steps (data/items.json exists):

    python3 scripts/prefill_config.py --project-name "<PlanGrid project name>" \
        [--version 0.1] [--project-folder <path>] [--building "<cover subtitle>"]

The report is built first and finished later (0.9.0), so nothing here waits on
the user. Every cover and scope fact comes from exactly one of these, and the
source is written to report.config.json "fact_sources" so a reviewer can see
where each value came from:

  profile    client-profile.json, the client-level facts of earlier reports:
             the project folder's own copy, else the one inside the newest
             package delivered there (copied to the workspace root)
  plangrid   the PlanGrid project name, the pin dates, the pin authors
  project name  the EPLUS naming convention "<CLIENT> - <BUILDING> - <EP no>"
             (STACK - POR03C - 27073): client, building and EP number, when
             the profile does not already state them
  task report   the Task Report PDF's header (scripts/task_report_to_pull.py
             writes it to ../plangrid_mcp/project.json): the site address, and
             the project name when --project-name is not given

Field result 2026-10-22: a run asked the user for the client, the building
and the EP number, all three printed in the Task Report header as the project
name, and set the address only because the model noticed it by hand.
  default    the house default (issuance date TBD, cover template,
             deleted pins dropped)
  user       set later by update_report.py from the user's answer
  missing    nobody has supplied it; the cover shows [MISSING: ...] and
             finish_list.py names the command that fills it

Never from memory: a memory note is private to one seat, invisible to the next
engineer and goes stale quietly (field result 2026-09-23: a run filled the
client, address, EP number and inspector from a memory note and labelled them
"the earlier report record"). A value already set by the user is never
overwritten; --force refills the rest.
"""
import argparse
import collections
import json
import os
import re
import sys
import zipfile

IDENTITY = ("cover_title", "cover_subtitle", "client_display_name", "site_address",
            "ep_project_no", "inspector", "inspection_date", "issuance_date")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def missing(v):
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip() or v.strip().startswith("<")
    if isinstance(v, list):
        return not v or all(missing(x) for x in v)
    if isinstance(v, dict):
        return all(missing(x) for x in v.values())
    return False


def slug(s):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s or "").strip("-")
    return s or "Project"


def split_project_name(name):
    """STACK - POR03C - 27073 -> ("STACK", "POR03C", "27073"); a name that does not
    follow the convention gives empty parts, never a guess."""
    parts = [x.strip() for x in re.split(r"\s+-\s+", name or "") if x.strip()]
    if len(parts) == 3 and re.fullmatch(r"\d{4,6}", parts[2]):
        return parts[0], parts[1], parts[2]
    if len(parts) == 2 and re.fullmatch(r"\d{4,6}", parts[1]):
        return parts[0], "", parts[1]
    return "", "", ""


def profile_from_package(folder):
    """client-profile.json from the newest *-Punch-Report-*.zip in folder, or {}."""
    best = None
    for f in os.listdir(folder):
        m = re.search(r"-DRAFT-v(\d+)\.(\d+)(?:-\d+)?\.zip$", f, re.I)
        if m:
            p = os.path.join(folder, f)
            key = (int(m.group(1)), int(m.group(2)), os.path.getmtime(p))
            if best is None or key > best[0]:
                best = (key, p)
    if not best:
        return {}
    try:
        with zipfile.ZipFile(best[1]) as z:
            return json.loads(z.read("client-profile.json").decode("utf-8"))
    except (KeyError, OSError, ValueError, zipfile.BadZipFile):
        return {}


def name_from_email(email):
    """leo.manning@eplusadvisors.com -> Leo Manning (a guess the finish list asks to confirm)."""
    local = (email or "").split("@")[0]
    parts = [p for p in re.split(r"[._\-]+", local) if p and not p.isdigit()]
    return " ".join(p.capitalize() for p in parts) if len(parts) >= 2 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project-name", default="",
                    help="the PlanGrid project name (list_projects / the pull); default: the Task Report header")
    ap.add_argument("--building", default="", help="the cover subtitle, only if a source on record states it")
    ap.add_argument("--version", default=None, help="draft version for the file name, from locate_inputs.py")
    ap.add_argument("--project-folder", default="", help="connected project folder (reads its client-profile.json)")
    ap.add_argument("--pipeline", default=".")
    ap.add_argument("--force", action="store_true", help="refill fields not set by the user")
    args = ap.parse_args()

    pipe = os.path.abspath(args.pipeline)
    ws = os.path.dirname(pipe)
    cfg_path = os.path.join(pipe, "build", "report.config.json")
    cfg = load(cfg_path, None)
    if cfg is None:
        sys.exit(f"ERROR: {cfg_path} not found; run init_workspace.sh first")
    items = load(os.path.join(pipe, "data", "items.json"), None)
    if items is None:
        sys.exit("ERROR: data/items.json not found; run the data steps (run_pipeline.sh) first")

    # The project folder's profile is the client-level record; bring it in once.
    # Since 2026-10-23 it travels inside the package rather than loose in the folder.
    ws_profile = os.path.join(ws, "client-profile.json")
    if args.project_folder and not load(ws_profile, {}).get("_from_project_folder"):
        src = os.path.join(args.project_folder, "client-profile.json")
        prof = load(src, None) if os.path.isfile(src) else None
        if prof is None and os.path.isdir(args.project_folder):
            prof = profile_from_package(args.project_folder) or None
        if prof:
            prof["_from_project_folder"] = True
            json.dump(prof, open(ws_profile, "w", encoding="utf-8"), indent=1)
    profile = load(ws_profile, {})
    sources = dict(cfg.get("fact_sources") or {})
    header = load(os.path.join(ws, "plangrid_mcp", "project.json"), {}) or {}
    project_name = args.project_name.strip() or str(header.get("name") or "").strip()
    pn_client, pn_building, pn_ep = split_project_name(project_name)

    def settable(key):
        return sources.get(key) != "user" and (args.force or missing(cfg.get(key)))

    def put(key, value, source):
        if not settable(key):
            return
        if missing(value):
            cfg[key] = [] if key == "site_address" else ""
            sources[key] = "missing"
        else:
            cfg[key] = value
            sources[key] = source

    # PlanGrid facts
    put("cover_title", project_name, "plangrid")
    pin_dates = sorted({str(i.get("created_at") or "")[:10] for i in items if i.get("created_at")})
    put("inspection_date", (pin_dates if len(pin_dates) > 1 else (pin_dates[0] if pin_dates else "")), "plangrid")

    # Client-level facts: the profile first, then the project name and the
    # Task Report header for whatever the profile does not state
    put("client_display_name", profile.get("client_display_name", ""), "profile")
    put("client_display_name", pn_client, "plangrid project name")
    put("site_address", profile.get("site_address") or [], "profile")
    put("site_address", [str(header["address"]).strip()] if header.get("address") else [], "task report header")
    put("ep_project_no", profile.get("ep_project_no", ""), "profile")
    put("ep_project_no", pn_ep, "plangrid project name")
    put("cover_subtitle", args.building.strip(), "plangrid")
    put("cover_subtitle", pn_building, "plangrid project name")
    if profile.get("cover_template"):
        put("cover_template", profile["cover_template"], "profile")
    insp = profile.get("inspector") or {}
    insp_name = insp.get("name") if isinstance(insp, dict) else str(insp)
    if not missing(insp_name):
        put("inspector", insp_name, "profile")
    else:
        # The pin author is who walked it far more often than not; a guess, so
        # its source says so and the finish list asks for confirmation.
        authors = collections.Counter(i.get("created_by") for i in items if i.get("created_by"))
        guess = name_from_email(authors.most_common(1)[0][0]) if authors else None
        put("inspector", guess or "", "plangrid (pin author, confirm)")

    # House defaults
    put("issuance_date", "TBD", "default")
    if settable("cover_mode") and missing(cfg.get("cover_mode")):
        cfg["cover_mode"] = profile.get("cover_mode") or "template"
        sources["cover_mode"] = "profile" if profile.get("cover_mode") else "default"
    if missing(cfg.get("deleted_pins")):
        cfg["deleted_pins"] = "drop"
        sources["deleted_pins"] = "default"

    # File name: <Project>-Punch-Report-DRAFT-v<version>.docx; the version comes
    # from the project folder's own deliveries (locate_inputs.py), never memory.
    out = str(cfg.get("output_filename") or "")
    if missing(out) or args.version or args.force:
        stem = slug(project_name or cfg.get("cover_title") or "")
        # "v0.1" and "0.1" both mean 0.1 (field result 2026-09-23: locate_inputs.py
        # prints "v0.1", and passing that on made "...-DRAFT-vv0.1.docx")
        ver = (args.version or "").strip().lstrip("vV") or (
            re.search(r"-DRAFT-v(\d+\.\d+)", out).group(1) if re.search(r"-DRAFT-v(\d+\.\d+)", out) else "0.1")
        cfg["output_filename"] = f"{stem}-Punch-Report-DRAFT-v{ver}.docx"
    if args.project_folder:
        cfg["delivery_folder"] = os.path.basename(os.path.normpath(args.project_folder))

    cfg["fact_sources"] = sources
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    print(f"config       : {os.path.relpath(cfg_path, pipe)}  ->  {cfg['output_filename']}")
    for key in IDENTITY + ("cover_mode", "deleted_pins"):
        val = cfg.get(key)
        shown = " | ".join(val) if isinstance(val, list) else (val if not missing(val) else "[MISSING]")
        print(f"  {key:<20}: {shown}   ({sources.get(key, 'template')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
