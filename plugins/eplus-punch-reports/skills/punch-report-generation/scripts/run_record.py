#!/usr/bin/env python3
"""
run_record.py -- write the run record from what the pipeline actually produced.

run_pipeline.sh calls this as its last step. It reads the artifacts on disk
(data/items.json, data/triage.json, build/master_report_items.json,
build/report.config.json, build/sheet_clip_dims_jpg.json, the verifier output
captured in build/verify_output.txt, the pull's photo_route.json) and writes:

  build/run.json          the machine-readable record of this run
  PROCESS-LOG.md          the block between <!-- run-record:start --> and
                          <!-- run-record:end --> (inputs, scope rules, counts,
                          drafting tally, verification, script versions)
  CLAUDE.md               the "**Current output:**" line and the block between
                          <!-- data-quality:start --> and <!-- data-quality:end -->

Nothing here is typed by a model. Field result 2026-09-10: a worker spent 7
minutes renumbering these same figures by hand after a scope change; now a
scope change is a re-run and the numbers follow. The hand-written sections of
PROCESS-LOG.md (scope decision, review rounds, limitations) are left alone.
If a file has no markers, the block is appended under a "Run record" heading.

    python3 scripts/run_record.py [--pull ../plangrid_pull] [--task-report "../X.pdf"]
                                  [--pipeline .] [--build build] [--data data]
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter

START, END = "<!-- run-record:start -->", "<!-- run-record:end -->"
DQ_START, DQ_END = "<!-- data-quality:start -->", "<!-- data-quality:end -->"
VERSIONED = ("gen_report.js", "verify_report.py", "build_master.py", "consolidate.py",
             "extract_sheet_clips.py", "adapt_mcp_pull.py", "run_pipeline.sh")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def md5short(path):
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except OSError:
        return "missing"


def replace_block(text, start, end, block, heading):
    if start in text and end in text:
        pre, rest = text.split(start, 1)
        _, post = rest.split(end, 1)
        return f"{pre}{start}\n{block}\n{end}{post}"
    return text.rstrip("\n") + f"\n\n{heading}\n\n{start}\n{block}\n{end}\n"


def fill_placeholders(text, facts):
    """Replace the template's identity placeholders with what the run knows.

    Only unambiguous tokens are touched: the project name, the version in an
    H1 line, and the README's file names, walk date and counts. Judgment
    placeholders (scope decision, limitations, lessons) are left for a person.
    Field result 2026-09-14: a delivered package still read "CTX2 v0.1" on the
    issues list and "<Project>" in the README after a v0.3 render.
    """
    out = text
    if facts.get("project"):
        out = out.replace("<PROJECT>", facts["project"]).replace("<Project>", facts["project"])
    if facts.get("building"):
        out = out.replace("<Building / area>", facts["building"])
    if facts.get("version"):
        out = re.sub(r"^(#.*?\bv)0\.1\b", lambda m: m.group(1) + facts["version"], out, flags=re.M)
    if facts.get("output"):
        out = out.replace("<report>-DRAFT-v0.1.docx", facts["output"])
    if facts.get("review"):
        out = out.replace("<report>-Review.xlsx", facts["review"])
    if facts.get("task_report"):
        out = out.replace("<Task Report>.pdf", facts["task_report"])
    if facts.get("pull"):
        out = out.replace("<pull folder>/", facts["pull"].rstrip("/") + "/")
    if facts.get("dates"):
        out = out.replace("<date>", facts["dates"])
    if facts.get("counts"):
        out = out.replace("<N> items, <N> pages, <N> photos", facts["counts"])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pipeline", default=".", help="the _pipeline folder (default: cwd)")
    ap.add_argument("--build", default="build")
    ap.add_argument("--data", default="data")
    ap.add_argument("--pull", default=None)
    ap.add_argument("--task-report", default=None)
    ap.add_argument("--no-docs", action="store_true", help="write build/run.json only")
    args = ap.parse_args()

    pipe = os.path.abspath(args.pipeline)
    build = os.path.join(pipe, args.build)
    data = os.path.join(pipe, args.data)
    prev = load(os.path.join(build, "run.json"), {})

    items = load(os.path.join(data, "items.json"), [])
    triage = load(os.path.join(data, "triage.json"), {})
    master = load(os.path.join(build, "master_report_items.json"), [])
    cfg = load(os.path.join(build, "report.config.json"), {})
    clips = load(os.path.join(build, "sheet_clip_dims_jpg.json"), {})
    sim = load(os.path.join(build, "sheet_clip_similarity.json"), {})
    pull = args.pull or prev.get("inputs", {}).get("pull")
    task_report = args.task_report or prev.get("inputs", {}).get("task_report")
    route = load(os.path.join(pull, "photo_route.json"), {}) if pull else {}
    try:
        with open(os.path.join(build, "verify_output.txt"), encoding="utf-8") as f:
            verify = f.read().strip()
    except OSError:
        verify = "(verify_report.py output not captured)"

    described = [i["number"] for i in items if (i.get("description") or "").strip()]
    photo_only = [i["number"] for i in items if not (i.get("description") or "").strip() and i.get("photos")]
    no_content = [i["number"] for i in items if not (i.get("description") or "").strip() and not i.get("photos")]
    valid_sheet = [i["number"] for i in items if i.get("sheet_name")]
    photos = sum(len(i.get("photos") or []) for i in items)
    photographers = Counter((p.get("photographer") or "unknown") for i in items for p in (i.get("photos") or []))
    dates = sorted({(p.get("captured") or "")[:8] for i in items for p in (i.get("photos") or []) if p.get("captured")})
    with_room = [i["number"] for i in items if (i.get("room") or "").strip()]
    origins = Counter(m.get("origin") or "unset" for m in master)
    confidence = Counter(m.get("confidence") or "unset" for m in master)
    with_precedent = [m.get("plangrid_ref") for m in master if m.get("precedent_note")]
    with_editor_note = [m.get("plangrid_ref") for m in master if m.get("editor_note")]
    scope = {k: os.environ.get(k) for k in ("SCOPE", "TITLE", "CREATED_AFTER", "DROP_PHRASES", "KEEP_DELETED")
             if os.environ.get(k)}
    if not scope and prev.get("scope_rules"):
        scope = prev["scope_rules"]
    output = os.path.join(build, cfg.get("output_filename", "")) if cfg.get("output_filename") else None
    docx = [f for f in glob.glob(os.path.join(build, "*.docx"))
            if not os.path.basename(f).startswith("~$") and not f.lower().endswith("-cover.docx")]
    newest = max(docx, key=os.path.getmtime) if docx else output
    cover_file = re.sub(r"\.docx$", "-Cover.docx", newest, flags=re.I) if newest else None
    cover_file = os.path.basename(cover_file) if cover_file and os.path.isfile(cover_file) else None
    verified_ok = "all checks passed" in verify

    rec = {
        "recorded_at": dt.datetime.now().isoformat(timespec="seconds"),
        "inputs": {"pull": pull, "task_report": task_report,
                   "photo_route": route.get("route", "unknown"), "photo_route_detail": route},
        "scope_rules": scope,
        "triage": triage,
        "clip_similarity": sim,
        "counts": {
            "items": len(items), "described": described, "photo_only": photo_only,
            "no_photos": no_content, "valid_sheet": len(valid_sheet), "photos": photos,
            # clip dims are keyed by file name (item_<N>.jpg); accept bare numbers too
            "sheet_clips": len(clips),
            "clip_missing": [i["number"] for i in items
                             if str(i["number"]) not in {re.sub(r"^item_(\d+)\.jpe?g$", r"\1", str(k)) for k in clips}],
            "with_room": len(with_room), "photographers": dict(photographers), "photo_dates": dates,
            "pin_dates": sorted({str(i.get("created_at") or "")[:10] for i in items if i.get("created_at")}),
            "deleted_retained": [i["number"] for i in items if i.get("deleted_in_plangrid")],
        },
        "drafting": {"origins": dict(origins), "confidence": dict(confidence),
                     "with_precedent_note": len(with_precedent), "with_editor_note": len(with_editor_note)},
        "output": {"file": os.path.basename(newest) if newest else None,
                   "cover_file": cover_file,
                   "cover_mode": cfg.get("cover_mode") or ("none" if cfg.get("include_cover") is False else "template"),
                   "size_mb": round(os.path.getsize(newest) / 1e6, 1) if newest and os.path.isfile(newest) else None,
                   "verified": verified_ok},
        "verify_output": verify,
        "scripts": {s: md5short(os.path.join(pipe, "scripts", s)) for s in VERSIONED},
    }
    os.makedirs(build, exist_ok=True)
    with open(os.path.join(build, "run.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    print(f"run record   : {os.path.join(args.build, 'run.json')}")

    if args.no_docs:
        return 0

    c = rec["counts"]
    tri = triage or {}
    dropped = {k: v for k, v in tri.items() if k.startswith("dropped_") and v}
    lines = [
        f"Generated by `scripts/run_record.py` at {rec['recorded_at']}. Do not edit inside the markers; re-run the pipeline instead.",
        "",
        "| Input | Value |",
        "|---|---|",
        f"| PlanGrid pull | `{pull or 'unknown'}` |",
        f"| Task Report PDF | `{task_report or 'none, items render (no pin clip)'}` |",
        "| Photo route | " + (f"{route['route']} ({route.get('live', 0)} live, {route.get('pdf', 0)} from PDF)" if route
                              else "not recorded (pre-exported pull, photos shipped with it)") + " |",
        f"| Scope rules | {', '.join(f'{k}={v}' for k, v in scope.items()) or 'none (every item in the pull)'} |",
        f"| Filler title dropped | {tri.get('filler_title') or 'none detected'} |",
        f"| Dropped by rule | {', '.join(f'{k[8:]} {v}' for k, v in dropped.items()) or 'none'} |",
        f"| Near misses reported | {', '.join('#' + str(n) for n, _ in tri.get('near_miss', [])) or 'none'} |",
        f"| Possible duplicates, shared photo | {', '.join(f'#{a} and #{b}' for a, b in tri.get('possible_duplicates', [])) or 'none'} |",
        f"| Adjacent pins, near-identical clips | {', '.join(f'#{a} and #{b}' for a, b, _ in sim.get('near_identical', [])) or 'none'} |",
        "",
        "| Count | Value |",
        "|---|---|",
        f"| Items in scope | {c['items']} |",
        f"| Pin dates (Date Recorded) | {', '.join(c['pin_dates']) or 'none in the pull'} |",
        f"| Deleted in PlanGrid, retained and marked | {c['deleted_retained'] or 'none'} |",
        f"| Authored description | {len(c['described'])} |",
        f"| Photo only | {len(c['photo_only'])} {c['photo_only'] or ''} |",
        f"| No description, no photos | {len(c['no_photos'])} {c['no_photos'] or ''} |",
        f"| Photos resolved | {c['photos']} (shot {', '.join(c['photo_dates']) or 'n/a'} by {', '.join(c['photographers']) or 'n/a'}) |",
        f"| Sheet clips | {c['sheet_clips']} found{', missing for ' + str(c['clip_missing']) if c['clip_missing'] else ''} |",
        f"| Valid sheet ref | {c['valid_sheet']} of {c['items']} |",
        f"| Sheet titles | {sum(1 for i in items if (i.get('sheet_description') or '').strip())} of {c['items']} items carry a sheet title"
        + ("" if all((i.get('sheet_description') or '').strip() for i in items) else
           " (MISSING: the MCP pull returns no sheet list; fill sheet_titles in the client profile)") + " |",
        f"| Room recorded | {c['with_room']} of {c['items']} |",
        "",
        "| Drafting | Value |",
        "|---|---|",
        f"| Origins | {', '.join(f'{k} {v}' for k, v in sorted(origins.items())) or 'no master yet'} |",
        f"| Confidence | {', '.join(f'{k} {v}' for k, v in sorted(confidence.items())) or 'n/a'} |",
        f"| Precedent note present | {len(with_precedent)} of {len(master)} (citations and documented gaps both count; see ISSUES-LIST for the split) |",
        f"| Editor's note present | {len(with_editor_note)} of {len(master)} |",
        "",
        f"Output: `{rec['output']['file']}` ({rec['output']['size_mb']} MB), cover_mode {rec['output']['cover_mode']}"
        + (f", cover file `{cover_file}`" if cover_file else "") + f", verifier {'passed' if verified_ok else 'FAILED or not run'}.",
        "",
        "```",
        verify,
        "```",
        "",
        "Scripts: " + ", ".join(f"{k} {v}" for k, v in rec["scripts"].items()),
    ]
    block = "\n".join(lines)

    # Identity placeholders, filled from the config and the artifacts on every
    # run so the paperwork never carries the template's name or version.
    out_name = rec["output"]["file"] or ""
    ver_m = re.search(r"-DRAFT-v(\d+(?:\.\d+)*)", out_name, flags=re.I)
    xlsx = [f for f in glob.glob(os.path.join(build, "*.xlsx")) if not os.path.basename(f).startswith("~$")]
    facts = {
        "project": (cfg.get("cover_title") or cfg.get("cover_subtitle") or cfg.get("client_display_name") or "").strip() or None,
        "building": (cfg.get("cover_subtitle") or "").strip() or None,
        "version": ver_m.group(1) if ver_m else None,
        "output": out_name or None,
        "review": os.path.basename(max(xlsx, key=os.path.getmtime)) if xlsx else None,
        "task_report": os.path.basename(task_report) if task_report else None,
        "pull": os.path.basename(os.path.normpath(pull)) if pull else None,
        "dates": " and ".join(c["pin_dates"]) if c["pin_dates"] else None,
        "counts": f"{c['items']} items, {c['photos']} photos" if c["items"] else None,
    }
    for name in ("ISSUES-LIST.md", "LESSONS-LEARNED.md", "PROCESS-LOG.md", "CLAUDE.md",
                 os.path.join("..", "README.md")):
        p = os.path.join(pipe, name)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as f:
            text = f.read()
        filled = fill_placeholders(text, facts)
        if filled != text:
            with open(p, "w", encoding="utf-8") as f:
                f.write(filled)
            print(f"placeholders : {os.path.normpath(name)} identity fields filled")

    plog = os.path.join(pipe, "PROCESS-LOG.md")
    if os.path.isfile(plog):
        with open(plog, encoding="utf-8") as f:
            text = f.read()
        with open(plog, "w", encoding="utf-8") as f:
            f.write(replace_block(text, START, END, block, "## Run record (generated)"))
        print("process log  : PROCESS-LOG.md run-record block updated")

    claude = os.path.join(pipe, "CLAUDE.md")
    if os.path.isfile(claude):
        with open(claude, encoding="utf-8") as f:
            text = f.read()
        cur = (f"**Current output:** `{rec['output']['file']}`, {c['items']} items, {c['photos']} photos, "
               f"{c['sheet_clips']} sheet clips (page count is Word's; open the file). "
               f"Draft for internal review, not issued.")
        # The line and any wrapped continuation up to the next blank line, so a
        # template that wrapped the sentence never leaves a dangling fragment
        # (field result 2026-09-14: "clips. Draft for internal review" was left
        # behind and had to be edited out by hand).
        text = re.sub(r"^\*\*Current output:\*\*.*(?:\n(?!\n).*)*", cur, text, count=1, flags=re.M)
        room_pct = round(100 * (c['items'] - c['with_room']) / c['items']) if c['items'] else 0
        dq = "\n".join([
            f"- {c['items']} items in scope, {len(c['described'])} with an authored description, {len(c['photo_only'])} photo-only",
            f"- {c['photos']} photos, all resolved to files on disk, shot {', '.join(c['photo_dates']) or 'n/a'} by {', '.join(c['photographers']) or 'n/a'}; photo route {rec['inputs']['photo_route']}",
            f"- `room` is empty on {room_pct}% of pins. The drawing sheet is the only location data.",
            f"- {c['valid_sheet']} of {c['items']} items resolve to a valid sheet; {c['sheet_clips']} sheet clips extracted",
            f"- filler title: {tri.get('filler_title') or 'none detected'}; scope rules: {', '.join(f'{k}={v}' for k, v in scope.items()) or 'none'}",
        ])
        text = replace_block(text, DQ_START, DQ_END, dq, "## Data quality (generated)")
        with open(claude, "w", encoding="utf-8") as f:
            f.write(text)
        print("manual       : CLAUDE.md current-output line and data-quality block updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
