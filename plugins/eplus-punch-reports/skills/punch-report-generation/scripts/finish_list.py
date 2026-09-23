#!/usr/bin/env python3
"""
finish_list.py -- what the built draft still needs, each with the command that supplies it.

run_pipeline.sh calls this after every verified render; run it by hand from
_pipeline/ with no arguments. It reads what the pipeline produced
(build/report.config.json, build/master_report_items.json, build/run.json,
data/items.json, data/triage.json) and writes:

  build/finish.json   the list, machine-readable
  ISSUES-LIST.md      the block between <!-- finish-list:start --> and
                      <!-- finish-list:end --> (appended if the markers are absent)
  stdout              the same list as markdown, for the final message

Why it exists (0.9.0): the report is built first with every decision at its
house default, and the questions come after. Users fire and forget; a run that
asked before building sat waiting for an answer and never produced a draft
(field result 2026-09-09: 47 minutes of waiting across three question rounds).
Now the draft always exists, and this list is the whole of what is left, split
into what blocks issuing and what is a review point. Every entry names one
update_report.py command, so supplying a missing piece is a surgical re-render,
not a rebuild.
"""
import argparse
import json
import os
import sys

START, END = "<!-- finish-list:start -->", "<!-- finish-list:end -->"
UPD = "python3 scripts/update_report.py"

LABELS = {
    "client_display_name": ("Client name", '--set client_display_name="<as it reads on the cover>"'),
    "site_address": ("Site address", '--set site_address="<street>, | <city, state>"'),
    "ep_project_no": ("EP project number", '--set ep_project_no=<number>'),
    "cover_subtitle": ("Building or area (cover subtitle)", '--set cover_subtitle="<Building A>"'),
    "inspector": ("Inspector (who walked it)", '--set inspector="<First Last>"'),
    "inspection_date": ("Walk date", '--set inspection_date=YYYY-MM-DD'),
}


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
    return False


def refs(nums):
    return ", ".join(f"#{n}" for n in nums)


def replace_block(text, block):
    if START in text and END in text:
        pre, rest = text.split(START, 1)
        _, post = rest.split(END, 1)
        return f"{pre}{START}\n{block}\n{END}{post}"
    lines = text.split("\n", 1)
    head, tail = (lines[0], lines[1] if len(lines) > 1 else "")
    # right under the H1, so the reviewer sees it first
    return f"{head}\n\n{START}\n{block}\n{END}\n{tail}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pipeline", default=".")
    ap.add_argument("--build", default="build")
    ap.add_argument("--data", default="data")
    ap.add_argument("--no-docs", action="store_true", help="write build/finish.json and stdout only")
    args = ap.parse_args()

    pipe = os.path.abspath(args.pipeline)
    build = os.path.join(pipe, args.build)
    data = os.path.join(pipe, args.data)
    cfg = load(os.path.join(build, "report.config.json"), {})
    master = load(os.path.join(build, "master_report_items.json"), [])
    items = load(os.path.join(data, "items.json"), [])
    triage = load(os.path.join(data, "triage.json"), {})
    run = load(os.path.join(build, "run.json"), {})
    sources = cfg.get("fact_sources") or {}

    blocking, review = [], []

    def add(lst, what, detail, cmd=None):
        lst.append({"what": what, "detail": detail, "command": f"{UPD} {cmd}" if cmd else None})

    # --- cover facts ------------------------------------------------------------
    for key, (label, cmd) in LABELS.items():
        val, src = cfg.get(key), str(sources.get(key) or "")
        if missing(val):
            add(blocking, label, "missing; the cover shows [MISSING]", cmd)
        elif "confirm" in src:
            add(blocking, label, f"'{val}' is a guess from {src.replace(', confirm', '')}; confirm or correct", cmd)
    iss = str(cfg.get("issuance_date") or "").strip()
    if missing(iss) or iss.upper() == "TBD":
        add(blocking, "Issuance date", "TBD on the cover; the reviewer decides it, it is never inferred",
            "--set issuance_date=YYYY-MM-DD")
    from_profile = [LABELS[k][0] for k in LABELS if sources.get(k) == "profile" and not missing(cfg.get(k))]
    if from_profile:
        add(review, "Facts from client-profile.json", ", ".join(from_profile)
            + " came from the project folder's client profile; confirm they are still current")

    # --- pin clips --------------------------------------------------------------
    counts = run.get("counts") or {}
    task_report = (run.get("inputs") or {}).get("task_report")
    in_report = {int(str(m.get("plangrid_ref", "#0")).lstrip("#") or 0) for m in master}
    clip_missing = [n for n in counts.get("clip_missing", []) if n in in_report]
    if not task_report:
        add(blocking, "Drawing pin clips", f"none: no PlanGrid Task Report PDF was available, so all "
            f"{len(master)} items read '(no pin clip)'. Export the Task Report from PlanGrid, put it in the "
            "project folder or upload it", '--task-report "<path to the Task Report PDF>"')
    elif clip_missing:
        add(review, "Drawing pin clips", f"no clip for {refs(clip_missing)} in {os.path.basename(task_report)}; "
            "a newer Task Report export may carry them", '--task-report "<newer Task Report PDF>"')

    # --- scope decisions made by default ------------------------------------------
    deleted = [i["number"] for i in items if i.get("deleted_in_plangrid")]
    if deleted:
        kept = str(cfg.get("deleted_pins") or "drop").lower() == "keep"
        if kept:
            add(review, "Pins deleted in PlanGrid", f"{refs(deleted)} kept with a red DELETED IN PLANGRID banner",
                "--deleted-pins drop")
        else:
            add(review, "Pins deleted in PlanGrid", f"{refs(deleted)} left out (the default), so the report's "
                "numbering skips them; keep them, bannered, to match PlanGrid", "--deleted-pins keep")
    near = [n for n, _ in triage.get("near_miss", [])]
    if near:
        add(review, "Near-miss record-only notes", f"{refs(near)} look like record-only notes but did not match a "
            "drop phrase exactly, so they are in the report", f"--drop {','.join(str(n) for n in near)}")
    dups = triage.get("possible_duplicates") or []
    if dups:
        add(review, "Possible duplicates", "; ".join(f"#{a} and #{b} share a photo" for a, b in dups)
            + ". Merge or drop one if they are the same condition", f"--drop <N>")
    pin_dates = counts.get("pin_dates") or []
    if len(pin_dates) > 1 and not (cfg.get("visit_sections") or cfg.get("visit_breaks")):
        add(review, "Two or more walk dates", f"{', '.join(pin_dates)}: one flat list, each item dated; "
            "add a 'Site Visit N' heading per date if wanted", "--set visit_sections=by_date")

    # --- items to review ------------------------------------------------------------
    def nums(pred):
        return [int(m["plangrid_ref"].lstrip("#")) for m in master if pred(m)]
    protected = ("user_reviewed", "reviewer_final")
    low = nums(lambda m: str(m.get("confidence") or "").lower() == "low" and m.get("origin") not in protected)
    undet = nums(lambda m: str(m.get("origin") or "") == "undetermined")
    inferred = nums(lambda m: str(m.get("origin") or "") == "photo_inferred" and m.get("origin") not in protected)
    nophoto = nums(lambda m: not m.get("photo_paths") and (m.get("photo_mode") or "own_photos") != "none")
    if undet:
        add(review, "Not determinable", f"{refs(undet)} ship marked not determinable (house policy); "
            "supply the condition if you know it", '--item <N> --description "..."')
    if low:
        add(review, "Low-confidence wording", f"{refs(low)}; each has an Editor's Note saying why",
            '--item <N> --description "..."')
    if inferred:
        add(review, "Wording inferred from photos", f"{refs(inferred)} had no usable note; the description "
            "states what the photos show", '--item <N> --description "..."')
    if nophoto:
        add(review, "Items without photos", f"{refs(nophoto)} carry an empty photo grid to paste into in Word; "
            "or remove the grid", "--item <N> --photo-mode none")

    # --- verification and delivery -------------------------------------------------
    if run and not (run.get("output") or {}).get("verified"):
        add(blocking, "Verification", "the last render did not pass verify_report.py; see build/verify_output.txt")
    if not cfg.get("delivery_folder"):
        add(blocking, "Delivery", "the report is in the session outputs folder, not a project folder. "
            "Connect the project folder in Cowork", '--deliver "<connected folder name>"')

    out_file = cfg.get("output_filename") or "(not rendered)"
    lines = [f"Generated by `scripts/finish_list.py` for `{out_file}`, {len(master)} items. "
             "Re-run after every change; do not edit inside the markers.", ""]
    if blocking:
        lines += [f"**Before it can be issued ({len(blocking)})**", ""]
        lines += [f"- **{e['what']}:** {e['detail']}." + (f" `{e['command']}`" if e["command"] else "") for e in blocking]
        lines.append("")
    if review:
        lines += [f"**Review points ({len(review)})**", ""]
        lines += [f"- **{e['what']}:** {e['detail']}." + (f" `{e['command']}`" if e["command"] else "") for e in review]
        lines.append("")
    if not blocking and not review:
        lines += ["Nothing outstanding: every cover fact is supplied, clips are in, and the draft verified.", ""]
    lines.append("Each command re-renders only what changed, verifies, and (with `--deliver`) delivers "
                 "the next version beside the earlier one.")
    block = "\n".join(lines)

    os.makedirs(build, exist_ok=True)
    with open(os.path.join(build, "finish.json"), "w", encoding="utf-8") as f:
        json.dump({"output": out_file, "blocking": blocking, "review": review}, f, indent=1)
    if not args.no_docs:
        il = os.path.join(pipe, "ISSUES-LIST.md")
        if os.path.isfile(il):
            with open(il, encoding="utf-8") as f:
                text = f.read()
            with open(il, "w", encoding="utf-8") as f:
                f.write(replace_block(text, block))
    print("## To finish this report\n")
    print(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
