#!/usr/bin/env bash
#
# init_workspace.sh -- stamp (or refresh) a punch report workspace from the plugin.
#
#     bash <plugin skill>/scripts/init_workspace.sh <workspace> [--from-package <zip>]
#
# The one supported way to build a workspace. Field result 2026-09-14: a worker
# copied template/ to <workspace>/_pipeline/template/ instead of <workspace>/,
# so the workspace had no CLAUDE.md, no build/assets, no report.config.json;
# the first render died on a missing logo, a config was written into the
# user's project folder by mistake, and the delivered package carried no
# documentation layer at all. This script lays the tree out the only way the
# pipeline reads it and refuses to finish if anything is missing.
#
# What it does, in order:
#   1. --from-package <zip>: unzips a previously delivered package into the
#      workspace (a re-run). Otherwise, a fresh workspace: copies template/.
#      into <workspace>/ so that <workspace>/_pipeline/CLAUDE.md,
#      <workspace>/client-profile.json and <workspace>/README.md exist.
#      Files already present are never overwritten (a second run on the same
#      workspace keeps the filled-in CLAUDE.md, config and profile).
#      The stamped tree is made writable straight away (see 3), before step 2
#      creates _pipeline/scripts inside it.
#   2. Refreshes <workspace>/_pipeline/scripts/ from THIS plugin checkout,
#      always. A package's scripts are never the source for a new run.
#   3. Makes everything under the workspace writable (copies off a read-only
#      plugin mount otherwise inherit the read-only bit; field result
#      2026-09-14: a worker could not edit its own workspace copy; field result
#      2026-09-23: the copied template dirs blocked step 2's mkdir).
#   4. Checks the layout and exits non-zero naming whatever is missing.
#
# Run it from the plugin path, not from a workspace copy: the template lives
# beside the plugin's scripts/, so the copy inside <workspace>/_pipeline/scripts/
# has nothing to stamp from and says so.
set -u

usage() { sed -n '3,6p' "$0"; }

WS=""
PKG=""
while [ $# -gt 0 ]; do
    case "$1" in
        --from-package) PKG="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        -*) echo "init_workspace.sh: unknown option $1" >&2; usage; exit 2 ;;
        *) if [ -z "$WS" ]; then WS="$1"; else echo "init_workspace.sh: one workspace path only" >&2; exit 2; fi; shift ;;
    esac
done
[ -n "$WS" ] || { usage; exit 2; }

HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(cd "$HERE/.." && pwd)"
if [ ! -d "$SKILL/template/_pipeline" ]; then
    echo "ERROR: $SKILL/template/_pipeline not found." >&2
    echo "       Run this script from the PLUGIN's scripts folder, not from a workspace copy:" >&2
    echo "       bash <plugin>/skills/punch-report-generation/scripts/init_workspace.sh <workspace>" >&2
    exit 1
fi

PY=""
for cand in python3 python; do
    if "$cand" -c 'import sys; sys.exit(0)' >/dev/null 2>&1; then PY="$cand"; break; fi
done

mkdir -p "$WS" || { echo "ERROR: cannot create $WS" >&2; exit 1; }
WS="$(cd "$WS" && pwd)"

# --- 1. package (re-run) or template (fresh) ---------------------------------
if [ -n "$PKG" ]; then
    [ -f "$PKG" ] || { echo "ERROR: package $PKG not found" >&2; exit 1; }
    [ -n "$PY" ] || { echo "ERROR: --from-package needs a python interpreter to unzip" >&2; exit 1; }
    "$PY" - "$PKG" "$WS" <<'PYUNZIP' || exit 1
import os, sys, zipfile
pkg, ws = sys.argv[1], sys.argv[2]
n = 0
with zipfile.ZipFile(pkg) as z:
    for info in z.infolist():
        name = info.filename
        # never let a package write outside the workspace or over the scripts
        if name.startswith(("/", "..")) or "/../" in name:
            continue
        if name.startswith("_pipeline/scripts/"):
            continue
        target = os.path.join(ws, name)
        if info.is_dir():
            os.makedirs(target, exist_ok=True)
            continue
        if os.path.exists(target):
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with z.open(info) as src, open(target, "wb") as dst:
            dst.write(src.read())
        n += 1
print(f"package      : {os.path.basename(pkg)} -> {n} files unpacked (existing files kept, scripts skipped)")
PYUNZIP
    mode="re-run from package"
else
    # cp -rn keeps whatever already exists, so a second stamp is harmless.
    # The trailing /. copies the CONTENTS of template/, which is the point.
    if [ -f "$WS/_pipeline/CLAUDE.md" ]; then
        mode="existing workspace (template files kept)"
    else
        mode="fresh workspace"
    fi
    cp -rn "$SKILL/template/." "$WS/" 2>/dev/null || {
        # BusyBox / older cp without -n: copy only what is missing
        (cd "$SKILL/template" && find . -type f) | while read -r f; do
            [ -e "$WS/$f" ] || { mkdir -p "$(dirname "$WS/$f")"; cp "$SKILL/template/$f" "$WS/$f"; }
        done
    }
fi

# Writable BEFORE step 2 creates anything inside the stamped tree. Field result
# 2026-09-23 (Cowork acceptance run, export 1790161330022): the plugin is mounted
# read-only in the VM (dr-x------), cp carries that mode onto the copied
# template directories, and the mkdir of _pipeline/scripts below failed with
# "Permission denied", leaving the workspace incomplete. Step 3 repeats this for
# the script files step 2 copies off the same mount.
chmod -R u+w "$WS" 2>/dev/null || true

# --- 2. scripts, always from the plugin --------------------------------------
mkdir -p "$WS/_pipeline/scripts"
(cd "$SKILL/scripts" && find . -type f \
    -not -path './node_modules/*' -not -path './__pycache__/*' -not -name '*.pyc') \
    | while read -r f; do
        mkdir -p "$(dirname "$WS/_pipeline/scripts/$f")"
        cp -f "$SKILL/scripts/$f" "$WS/_pipeline/scripts/$f"
    done

# --- 3. writable -------------------------------------------------------------
chmod -R u+w "$WS" 2>/dev/null || true

# --- 4. check ----------------------------------------------------------------
missing=0
need() { [ -e "$WS/$1" ] && printf '  [OK]   %s\n' "$1" || { printf '  [MISSING] %s\n' "$1"; missing=$((missing+1)); }; }
echo "init_workspace: $WS  ($mode)"
echo "  plugin skill : $SKILL"
need "_pipeline/CLAUDE.md"
need "_pipeline/PROCESS-LOG.md"
need "_pipeline/ISSUES-LIST.md"
need "_pipeline/LESSONS-LEARNED.md"
need "_pipeline/handoff/HANDOFF.md"
need "_pipeline/build/report.config.json"
need "_pipeline/build/assets/logos/ep_logo.jpg"
need "_pipeline/build/assets/logos/ep_url.png"
need "_pipeline/build/assets/cover/cover_hero.jpg"
need "_pipeline/build/assets/cover/cover_bands.png"
need "_pipeline/scripts/run_pipeline.sh"
need "_pipeline/scripts/gen_report.js"
need "_pipeline/scripts/package.py"
need "client-profile.json"
need "README.md"
mkdir -p "$WS/_pipeline/data" "$WS/_pipeline/build/thumbs_uniform" "$WS/_pipeline/build/sheet_clips_jpg" \
         "$WS/_pipeline/build/_scratch" "$WS/_pipeline/review" "$WS/_pipeline/handoff/memory"
for stray in "_pipeline/template" "_pipeline/templates"; do
    if [ -e "$WS/$stray" ]; then
        printf '  [WARN] %s exists: a template stamped into the wrong place; the packager skips it\n' "$stray"
    fi
done
if [ ! -w "$WS/_pipeline/scripts/build_master.py" ]; then
    printf '  [MISSING] _pipeline/scripts is not writable\n'; missing=$((missing+1))
fi

if [ "$missing" -gt 0 ]; then
    echo "ERROR: workspace incomplete ($missing missing); do not run the pipeline in it." >&2
    exit 1
fi
echo "  next         : cd \"$WS/_pipeline\" && bash scripts/install_deps.sh && bash scripts/smoke_test.sh"
