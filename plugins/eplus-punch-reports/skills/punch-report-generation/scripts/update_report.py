#!/usr/bin/env python3
"""
update_report.py -- surgical edits to a built punch report: change what changed, re-render, deliver.

Run from the workspace's _pipeline/ (the same workspace, or one rebuilt from
the delivered package with init_workspace.sh --from-package in a new session):

    python3 scripts/update_report.py [changes ...] [--deliver [<folder>]] [--replace]

Changes (any number, in one call):
  --set KEY=VALUE        a cover fact the user supplied. Keys: client_display_name,
                         site_address (lines split on "|"), ep_project_no,
                         cover_subtitle, cover_title, cover_eyebrow, inspector,
                         reviewer (profile only), inspection_date (comma list),
                         issuance_date (YYYY-MM-DD, MM/DD/YYYY or TBD), cover_mode,
                         visit_sections (by_date | none), footer_text.
                         Source recorded as "user"; client-level facts are also
                         written to client-profile.json for the next report.
  --deleted-pins keep|drop   pins PlanGrid deleted: keep them bannered, or leave them out
  --drop N[,N]           leave these pins out of the report (drafted_items.json "omit")
  --restore N[,N]        put dropped pins back
  --item N [--title T] [--description D] [--corrective-action C]
           [--editor-note E] [--photo-mode own_photos|none|followup]
                         reword one item; approved text becomes origin user_reviewed
  --edits FILE.json      many items at once: [{"number": N, "description": "...", ...}]
  --task-report PDF      a Task Report PDF arrived: copy it in, cut the pin clips,
                         re-render (the only step that re-reads a PDF)
  --scope / --title-filter / --created-after / --drop-phrases
                         a scope change: the data steps re-run, then the render
  --version X.Y          force the draft version in the file name

Then it re-renders (build master, render, verify, run record, review sheet,
finish list; about a minute) unless --no-render, logs the change in
PROCESS-LOG.md, and with --deliver packages the new version into the project
folder. The version steps up automatically (v0.1 -> v0.2) when the current
file name is already delivered there, so an earlier delivery is never
overwritten. --deliver with no folder uses the folder recorded at the first
delivery; a folder is found by name under /sessions/*/mnt/ ("outputs" for the
session outputs folder).

Why it exists (0.9.0): supplying a missing piece used to mean a worker rerunning
the stage and a fresh round of reading references; a user who handed over an
EP number and a walker's name waited 8 minutes for a render (field result
2026-09-09). A cover fact, a reworded item or a new Task Report is one command.
"""
import argparse
import datetime as dt
import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_KEYS = {"client_display_name", "site_address", "ep_project_no", "cover_subtitle", "cover_title",
            "cover_eyebrow", "inspector", "reviewer", "inspection_date", "issuance_date", "cover_mode",
            "visit_sections", "footer_text"}
PROFILE_KEYS = {"client_display_name", "site_address", "ep_project_no", "inspector", "reviewer", "cover_mode"}
COVER_MODES = {"template", "supplied", "blank", "none"}
PHOTO_MODES = {"own_photos", "none", "followup"}
VERSION_RE = re.compile(r"-DRAFT-v(\d+)\.(\d+)", re.I)
REV_START, REV_END = "<!-- revisions:start -->", "<!-- revisions:end -->"


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def sanitize_fn():
    spec = importlib.util.spec_from_file_location("build_master", os.path.join(HERE, "build_master.py"))
    bm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bm)
    return bm.sanitize


def iso_date(v):
    s = v.strip()
    if s.upper() == "TBD":
        return "TBD"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return s
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    sys.exit(f"ERROR: date {v!r} is not YYYY-MM-DD, MM/DD/YYYY or TBD")


def nums(csv):
    try:
        return [int(x.strip().lstrip("#")) for x in csv.split(",") if x.strip()]
    except ValueError:
        sys.exit(f"ERROR: {csv!r} is not a comma list of PlanGrid numbers")


def resolve_folder(name, mnt_glob):
    if not name:
        return None
    if os.path.isabs(name) and os.path.isdir(name):
        return name
    if os.path.isdir(name):
        return os.path.abspath(name)
    for mnt in sorted(glob.glob(mnt_glob)):
        cand = os.path.join(mnt, name)
        if os.path.isdir(cand):
            return cand
    return None


def versions_in(folder):
    out = []
    for f in os.listdir(folder):
        m = VERSION_RE.search(f)
        if m:
            out.append((int(m.group(1)), int(m.group(2))))
    return out


def set_version(fname, ver):
    if VERSION_RE.search(fname):
        return VERSION_RE.sub(f"-DRAFT-v{ver}", fname, count=1)
    return re.sub(r"\.docx$", f"-DRAFT-v{ver}.docx", fname, flags=re.I)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--deleted-pins", choices=["keep", "drop"])
    ap.add_argument("--drop", default="")
    ap.add_argument("--restore", default="")
    ap.add_argument("--item", type=int)
    ap.add_argument("--title")
    ap.add_argument("--description")
    ap.add_argument("--corrective-action")
    ap.add_argument("--editor-note")
    ap.add_argument("--photo-mode", choices=sorted(PHOTO_MODES))
    ap.add_argument("--edits", help="JSON list of item edits")
    ap.add_argument("--task-report")
    ap.add_argument("--scope")
    ap.add_argument("--title-filter")
    ap.add_argument("--created-after")
    ap.add_argument("--drop-phrases")
    ap.add_argument("--version")
    ap.add_argument("--deliver", nargs="?", const="", default=None, metavar="FOLDER")
    ap.add_argument("--replace", action="store_true", help="overwrite a delivery of the same name (only when asked)")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--pipeline", default=".")
    ap.add_argument("--mnt-glob", default="/sessions/*/mnt", help=argparse.SUPPRESS)
    args = ap.parse_args()

    t0 = time.time()
    pipe = os.path.abspath(args.pipeline)
    ws = os.path.dirname(pipe)
    cfg_path = os.path.join(pipe, "build", "report.config.json")
    drafted_path = os.path.join(pipe, "data", "drafted_items.json")
    profile_path = os.path.join(ws, "client-profile.json")
    cfg = load(cfg_path, None)
    if cfg is None:
        sys.exit(f"ERROR: {cfg_path} not found. Run from the workspace's _pipeline/ folder; in a new "
                 "session rebuild the workspace first: init_workspace.sh <ws> --from-package <zip>")
    drafted = load(drafted_path, None)
    profile = load(profile_path, {})
    sources = dict(cfg.get("fact_sources") or {})
    changes, data_rerun = [], False

    # --- cover facts ----------------------------------------------------------------
    for kv in args.set:
        if "=" not in kv:
            sys.exit(f"ERROR: --set needs KEY=VALUE, got {kv!r}")
        key, val = kv.split("=", 1)
        key, val = key.strip(), val.strip()
        if key not in CFG_KEYS:
            sys.exit(f"ERROR: unknown key {key!r}; one of {', '.join(sorted(CFG_KEYS))}")
        if key == "site_address":
            value = [ln.strip() for ln in val.split("|") if ln.strip()]
        elif key == "inspection_date":
            ds = [iso_date(x) for x in val.split(",") if x.strip()]
            value = ds if len(ds) > 1 else (ds[0] if ds else "")
        elif key == "issuance_date":
            value = iso_date(val)
        elif key == "cover_mode":
            if val not in COVER_MODES:
                sys.exit(f"ERROR: cover_mode must be one of {sorted(COVER_MODES)}")
            value = val
        elif key == "visit_sections":
            if val not in ("by_date", "none"):
                sys.exit("ERROR: visit_sections is by_date or none")
            value = None if val == "none" else val
        else:
            value = val
        if key != "reviewer":
            if value is None:
                cfg.pop(key, None)
            else:
                cfg[key] = value
            sources[key] = "user"
        if key in PROFILE_KEYS:
            if key in ("inspector", "reviewer"):
                old = profile.get(key)
                profile[key] = {"name": value, "title": old.get("title", "") if isinstance(old, dict) else ""}
            else:
                profile[key] = value
        changes.append(f"set {key}={' | '.join(value) if isinstance(value, list) else value}")

    if args.deleted_pins:
        cfg["deleted_pins"] = args.deleted_pins
        sources["deleted_pins"] = "user"
        changes.append(f"deleted pins: {args.deleted_pins}")

    # --- judgment layer -------------------------------------------------------------------
    item_edits = []
    if args.edits:
        item_edits += load(args.edits, None) or sys.exit(f"ERROR: {args.edits} is not a JSON list")
    if args.item is not None:
        e = {"number": args.item}
        for f in ("title", "description", "corrective_action", "editor_note", "photo_mode"):
            v = getattr(args, f)
            if v is not None:
                e[f] = v
        if len(e) == 1:
            sys.exit("ERROR: --item needs at least one of --title --description --corrective-action "
                     "--editor-note --photo-mode")
        item_edits.append(e)
    if (item_edits or args.drop or args.restore) and drafted is None:
        sys.exit(f"ERROR: {drafted_path} not found; draft the items first")
    if isinstance(drafted, list):
        drafted = {"items": drafted, "merges": [], "omit": []}
    if drafted is not None:
        drafted.setdefault("omit", [])
    if args.drop:
        for n in nums(args.drop):
            if n not in drafted["omit"]:
                drafted["omit"].append(n)
        changes.append(f"drop {', '.join('#' + str(n) for n in nums(args.drop))}")
    if args.restore:
        back = set(nums(args.restore))
        drafted["omit"] = [n for n in drafted["omit"] if n not in back]
        changes.append(f"restore {', '.join('#' + str(n) for n in sorted(back))}")
    if item_edits:
        sanitize = sanitize_fn()
        by_num = {int(d["number"]): d for d in drafted["items"]}
        for e in item_edits:
            # "item" is accepted for "number" (field result 2026-09-23: a batch file
            # keyed by "item" died on a KeyError)
            key = "number" if "number" in e else ("item" if "item" in e else None)
            if key is None:
                sys.exit(f"ERROR: every --edits entry needs \"number\" (the PlanGrid number): {e}")
            n = int(str(e[key]).lstrip("#"))
            entry = by_num.get(n)
            if entry is None:
                if not (e.get("title") and e.get("description")):
                    sys.exit(f"ERROR: #{n} has no drafted entry; a new entry needs --title and --description")
                entry = {"number": n}
                drafted["items"].append(entry)
                by_num[n] = entry
            touched = []
            for f in ("title", "description", "corrective_action"):
                if f in e:
                    clean = sanitize(re.sub(r"\s*[–—]\s*", ", ", e[f]))
                    if clean != e[f]:
                        print(f"note         : #{n} {f}: dashes replaced per the house rule")
                    entry[f] = clean
                    touched.append(f)
            if touched:
                entry["origin"] = "user_reviewed"
                entry["confidence"] = "reviewer approved"
            if "editor_note" in e:
                entry["editor_note"] = e["editor_note"] or None
                touched.append("editor_note")
            if "photo_mode" in e:
                if e["photo_mode"] not in PHOTO_MODES:
                    sys.exit(f"ERROR: photo_mode must be one of {sorted(PHOTO_MODES)}")
                entry["photo_mode"] = e["photo_mode"]
                touched.append("photo_mode")
            changes.append(f"#{n}: {', '.join(touched)}")

    # --- a Task Report PDF arrived --------------------------------------------------------------
    env = dict(os.environ, PYTHONUTF8="1")
    if args.task_report:
        src = args.task_report
        if not os.path.isfile(src):
            sys.exit(f"ERROR: {src} not found")
        dst = os.path.join(ws, os.path.basename(src))
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)
        env["TASK_REPORT"] = dst
        changes.append(f"task report {os.path.basename(dst)}")

    # --- scope change: the data steps re-run ---------------------------------------------------------
    for opt, var in (("scope", "SCOPE"), ("title_filter", "TITLE"), ("created_after", "CREATED_AFTER"),
                     ("drop_phrases", "DROP_PHRASES")):
        v = getattr(args, opt)
        if v is not None:
            env[var] = v
            data_rerun = True
            changes.append(f"{var}={v}")

    # --- where it goes, and under which version ---------------------------------------------------
    dest = None
    if args.deliver is not None:
        name = args.deliver or cfg.get("delivery_folder") or ""
        if name == "outputs" or (not name and not cfg.get("delivery_folder")):
            dest = resolve_folder("outputs", args.mnt_glob)
        else:
            dest = resolve_folder(name, args.mnt_glob)
        if not dest:
            conn = [os.path.basename(p) for m in glob.glob(args.mnt_glob) for p in glob.glob(os.path.join(m, "*"))
                    if os.path.isdir(p) and not os.path.basename(p).startswith(".")]
            sys.exit(f"ERROR: folder {name!r} is not connected to this session. Connected: "
                     f"{', '.join(conn) or 'none'}. Ask the user to connect it in Cowork, then --deliver <name>.")
        if os.path.basename(os.path.normpath(dest)) != "outputs":
            cfg["delivery_folder"] = os.path.basename(os.path.normpath(dest))
    out = str(cfg.get("output_filename") or "")
    if args.version:
        cfg["output_filename"] = set_version(out, args.version.strip().lstrip("vV"))
    elif dest and not args.replace and os.path.exists(os.path.join(dest, out)):
        have = versions_in(dest)
        hi = max(have) if have else (0, 1)
        cfg["output_filename"] = set_version(out, f"{hi[0]}.{hi[1] + 1}")
    if cfg.get("output_filename") != out:
        changes.append(f"version {out} -> {cfg['output_filename']}")

    if not changes and args.deliver is None and not args.no_render:
        print("nothing to change; re-rendering as it stands")
    cfg["fact_sources"] = sources
    save(cfg_path, cfg)
    if drafted is not None:
        save(drafted_path, drafted)
    if profile:
        save(profile_path, profile)
    for c in changes:
        print(f"change       : {c}")

    # --- re-render ----------------------------------------------------------------------------------
    if args.task_report:
        r = subprocess.run([sys.executable, "scripts/extract_sheet_clips.py", env["TASK_REPORT"], "build/sheet_clips_jpg",
                            "--items-from", "data/items.json", "--dims-out", "build/sheet_clip_dims_jpg.json"],
                           cwd=pipe, env=env, capture_output=True, text=True)
        print((r.stdout + r.stderr).strip()[-1200:])
        if r.returncode != 0:
            sys.exit("ERROR: sheet clip extraction failed; the report was not re-rendered")
    if not args.no_render:
        if not data_rerun:
            env["RENDER_ONLY"] = "1"
        # PIPELINE_BASH: the smoke test on a Windows dev box points this at Git Bash
        # (a bare "bash" from Windows python resolves to WSL); the sandbox needs nothing.
        bash = os.environ.get("PIPELINE_BASH") or "bash"
        r = subprocess.run([bash, "scripts/run_pipeline.sh"], cwd=pipe, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        log = r.stdout + r.stderr
        with open(os.path.join(pipe, "build", "update_render.log"), "w", encoding="utf-8") as f:
            f.write(log)
        if r.returncode != 0:
            print(log[-3000:])
            sys.exit(f"ERROR: the re-render failed (exit {r.returncode}); full log in build/update_render.log. "
                     "The changes above are saved in the config and drafts, but the report in build/ is from "
                     "before them and nothing was delivered. Fix what the log names and run again.")
        fails = [ln.strip() for ln in log.splitlines() if "[FAIL]" in ln]
        verdict = "all checks passed" if "all checks passed" in log else "see build/verify_output.txt"
        print(f"render       : {cfg['output_filename']}  (verify: {verdict}{'; ' + '; '.join(fails) if fails else ''})")

    # --- revision log -------------------------------------------------------------------------------------
    plog = os.path.join(pipe, "PROCESS-LOG.md")
    if changes and os.path.isfile(plog):
        with open(plog, encoding="utf-8") as f:
            text = f.read()
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        line = f"- {stamp}, `{cfg['output_filename']}`: " + "; ".join(changes)
        if REV_START in text and REV_END in text:
            pre, rest = text.split(REV_START, 1)
            body, post = rest.split(REV_END, 1)
            body = body.strip("\n")
            text = f"{pre}{REV_START}\n{(body + chr(10)) if body else ''}{line}\n{REV_END}{post}"
        else:
            text = text.rstrip("\n") + (f"\n\n## Revisions (update_report.py)\n\n"
                                        f"{REV_START}\n{line}\n{REV_END}\n")
        with open(plog, "w", encoding="utf-8") as f:
            f.write(text)

    # --- deliver --------------------------------------------------------------------------------------------
    if dest:
        cmd = [sys.executable, "scripts/package.py", ws, dest] + (["--replace"] if args.replace else [])
        r = subprocess.run(cmd, cwd=pipe, env=env, capture_output=True, text=True)
        print((r.stdout + r.stderr).strip())
        if r.returncode != 0:
            sys.exit("ERROR: delivery failed; the render in build/ is current, fix the message above and "
                     "run with --deliver again")
    fin = load(os.path.join(pipe, "build", "finish.json"), {})
    if fin:
        print(f"finish list  : {len(fin.get('blocking', []))} item(s) block issuing, "
              f"{len(fin.get('review', []))} review point(s); python3 scripts/finish_list.py --no-docs prints them")
    print(f"done in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
