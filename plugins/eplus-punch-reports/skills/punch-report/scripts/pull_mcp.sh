#!/usr/bin/env bash
# Fetch the plangrid MCP's result packets into the workspace.
#
#   bash scripts/pull_mcp.sh '<packet url>[#<sha256>]' ['<packet url>[#<sha256>]' ...]
#
# Each get_tasks / list_sheets / pull_tasks / get_photos summary carries a
# `packet` {url, bytes, sha256, fetch}. Pass the url, and the sha256 after a
# '#', for each packet you need; the file name is the last path segment
# (tasks.json, sheets.json, photos.json) and lands in --dest (default
# ../plangrid_mcp, beside _pipeline/). The sha check proves the file on disk
# is the server's file: no model ever types this JSON. Exits nonzero on a
# failed fetch (404 = packet expired, call the tool again), a sha mismatch,
# or invalid JSON. Always prints one line per file.
set -u
dest="../plangrid_mcp"
args=()
while [ $# -gt 0 ]; do
    case "$1" in
        --dest) dest="$2"; shift 2 ;;
        -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
        *) args+=("$1"); shift ;;
    esac
done
if [ ${#args[@]} -eq 0 ]; then
    echo "usage: bash scripts/pull_mcp.sh '<packet url>[#<sha256>]' ..." >&2
    exit 2
fi
PY=""
for c in python3 python; do
    if "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "pull_mcp.sh: no working python3/python on PATH" >&2; exit 2; }
mkdir -p "$dest"
# curl's stderr goes to a PRIVATE temp file. /tmp is shared between sandbox
# sessions (mounted nobody:nogroup, sticky), so a fixed /tmp/pull_mcp.err left
# by another session is unwritable here and bash aborts the whole command on
# the failed redirect: curl never runs and the script reports "FETCH FAILED
# (HTTP none; )", which reads like an egress block. Field result 2026-09-14.
err="$(mktemp "${TMPDIR:-/tmp}/pull_mcp.XXXXXX" 2>/dev/null || echo "$dest/.pull_mcp.$$.err")"
trap 'rm -f "$err"' EXIT
rc=0
for spec in "${args[@]}"; do
    url="${spec%%#*}"
    sha=""
    [ "$spec" != "$url" ] && sha="${spec#*#}"
    name="${url##*/}"
    case "$name" in
        *.json) ;;
        *) echo "$name: not a packet url (expected .../files/<job>/<name>.json)"; rc=1; continue ;;
    esac
    out="$dest/$name"
    code=$(curl -sS -o "$out" -w '%{http_code}' "$url" 2>"$err" || true)
    if [ "$code" != "200" ]; then
        echo "$name: FETCH FAILED (HTTP ${code:-none}; $(head -c 120 "$err" 2>/dev/null))"
        [ "$code" = "404" ] && echo "   the packet expired or the url is wrong: call the MCP tool again for a fresh one"
        rm -f "$out"; rc=1; continue
    fi
    if [ -n "$sha" ]; then
        got=$("$PY" -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$out")
        if [ "$got" != "$sha" ]; then
            echo "$name: SHA256 MISMATCH (expected $sha, got $got); file removed"
            rm -f "$out"; rc=1; continue
        fi
        shanote="sha ok"
    else
        shanote="sha not checked"
    fi
    summary=$("$PY" - "$out" <<'PYEOF'
import json, sys
p = sys.argv[1]
try:
    d = json.load(open(p, encoding="utf-8"))
except Exception as e:
    print(f"INVALID JSON: {e}"); sys.exit(1)
if isinstance(d, dict) and "tasks" in d:
    tasks = d["tasks"]
    photos = sum(len(t.get("photos") or []) for t in tasks)
    served = sum(1 for t in tasks for ph in (t.get("photos") or []) if ph.get("download_url"))
    print(f"{len(tasks)} tasks, {photos} photos ({served} with download_url)")
elif isinstance(d, dict) and "sheets" in d:
    sheets = d["sheets"]
    titled = sum(1 for s in sheets if s.get("description"))
    print(f"{len(sheets)} sheets, {titled} titled")
elif isinstance(d, dict) and "photos" in d:
    print(f"{len(d['photos'])} photos")
else:
    print("json ok")
PYEOF
) || { echo "$name: $summary"; rm -f "$out"; rc=1; continue; }
    echo "$name: $summary, $(wc -c < "$out" | tr -d ' ') bytes, $shanote -> $out"
done
exit $rc
