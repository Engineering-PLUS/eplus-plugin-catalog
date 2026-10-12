#!/usr/bin/env bash
# Fetch a PlanGrid Task Report PDF from its signed download link into the
# workspace, and record how the run got (or did not get) its Task Report.
#
#   bash scripts/fetch_task_report.sh '<signed S3 url>' [--staple <staple url>]
#   bash scripts/fetch_task_report.sh --skipped "<reason>" [--staple <staple url>] [--report-name "<name>"]
#
# The url is the one the Download button on the report's /staple/<id> page
# opens (reference/task-report-export.md). It carries its own signature and is
# good for 30 days, so curl needs no PlanGrid login, only egress to
# plangrid-reports-prod-reportsresults-19fdmf8y8pfpb.s3.amazonaws.com.
# The PDF lands in --dest (default .., beside _pipeline/) as
# "<PlanGrid report name>.pdf", where run_pipeline.sh finds it. It is checked
# to be a whole PDF (%PDF header, %%EOF trailer), never trusted by status code.
# Every call writes <dest>/task_report_route.json for run_record.py, so the
# PROCESS-LOG says which route the Task Report took. The url's query string
# (the signature) is never printed. Exits nonzero when no PDF was saved.
set -u
dest=".."
url=""
skipped=""
staple=""
report_name=""
while [ $# -gt 0 ]; do
    case "$1" in
        --dest) dest="$2"; shift 2 ;;
        --skipped) skipped="$2"; shift 2 ;;
        --staple) staple="$2"; shift 2 ;;
        --report-name) report_name="$2"; shift 2 ;;
        -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
        *) url="$1"; shift ;;
    esac
done
PY=""
for c in python3 python; do
    if "$c" -c "import sys" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "fetch_task_report.sh: no working python3/python on PATH" >&2; exit 2; }
if [ -z "$url" ] && [ -z "$skipped" ]; then
    echo "usage: bash scripts/fetch_task_report.sh '<signed url>' | --skipped \"<reason>\"" >&2
    exit 2
fi
mkdir -p "$dest"

# record <status> <reason> [file] [bytes] [host]
record() {
    "$PY" - "$dest/task_report_route.json" "$1" "$2" "${3:-}" "${4:-}" "${5:-}" "$staple" "$report_name" <<'PYEOF'
import datetime, json, sys
path, status, reason, file, size, host, staple, name = sys.argv[1:9]
rec = {"route": "browser export", "status": status, "reason": reason or None,
       "file": file or None, "bytes": int(size) if size else None, "host": host or None,
       "staple": staple or None, "report_name": name or None,
       "recorded_at": datetime.datetime.now().isoformat(timespec="seconds")}
with open(path, "w", encoding="utf-8") as f:
    json.dump(rec, f, indent=1)
PYEOF
}

if [ -n "$skipped" ]; then
    record skipped "$skipped"
    echo "task report : not fetched ($skipped); recorded in $dest/task_report_route.json"
    exit 0
fi

# Host, file name and report name from the url, without echoing the signature.
parsed=$("$PY" - "$url" "$report_name" <<'PYEOF'
import os, re, sys
from urllib.parse import urlsplit, parse_qs
url, name = sys.argv[1], sys.argv[2]
u = urlsplit(url)
host = u.netloc.lower()
test_host = os.environ.get("TASK_REPORT_TEST_HOST", "").lower()
ok = (u.scheme == "https" and host.startswith("plangrid-reports-") and host.endswith(".s3.amazonaws.com")) \
     or (test_host and host == test_host)
if not ok:
    print(f"BAD\t{host or '(no host)'}"); sys.exit(0)
if not name:
    cd = (parse_qs(u.query).get("response-content-disposition") or [""])[0]
    m = re.search(r'filename="?([^";]+)', cd)
    name = re.sub(r"\.pdf$", "", (m.group(1) if m else ""), flags=re.I).replace("_", " ").strip()
name = re.sub(r'[\\/:*?"<>|]+', "-", name).strip() or "PlanGrid Task Report"
if "task report" not in name.lower():
    name = "PlanGrid Task Report - " + name
print(f"OK\t{host}\t{name}")
PYEOF
)
IFS=$'\t' read -r verdict host name <<<"$parsed"
if [ "$verdict" != "OK" ]; then
    echo "task report : REFUSED, $host is not a PlanGrid report download link."
    echo "   Pass the link the Download button on the /staple/<id> page opens"
    echo "   (https://plangrid-reports-...s3.amazonaws.com/...), not the staple page itself."
    record fallback "not a PlanGrid report link ($host)" "" "" "$host"
    exit 2
fi
[ -n "$report_name" ] || report_name="$name"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/task_report.XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT
part="$tmpdir/report.pdf"
code=$(curl -sS -L -o "$part" -w '%{http_code}' "$url" 2>"$tmpdir/err" || true)
if [ "$code" != "200" ]; then
    why="HTTP ${code:-none}"
    body=$(head -c 400 "$part" 2>/dev/null | tr -s '\r\n\t ' ' ' | head -c 200)
    errline=$(head -c 160 "$tmpdir/err" 2>/dev/null | tr -s '\r\n' ' ')
    case "$code" in
        000|"") hint="could not connect to $host: the sandbox's egress allowlist probably does not include it. File it with request_egress_allow (error-reporting skill) naming $host." ;;
        403) case "$body" in
                 *xpired*) hint="the signed link expired (30 days): click Download on the staple page again for a fresh one." ;;
                 *AccessDenied*|*SignatureDoesNotMatch*) hint="S3 refused the link: it was cut or retyped. Pass it exactly as the page returned it." ;;
                 *) hint="refused before it reached S3, likely the egress proxy: file $host with request_egress_allow." ;;
             esac ;;
        *) hint="unexpected response from $host." ;;
    esac
    echo "task report : FETCH FAILED ($why; ${errline:-$body})"
    echo "   $hint"
    record fallback "$why: $hint" "" "" "$host"
    exit 1
fi
size=$(wc -c < "$part" | tr -d ' ')
head5=$(head -c 5 "$part")
if [ "$head5" != "%PDF-" ] || ! tail -c 2048 "$part" | grep -aq '%%EOF'; then
    echo "task report : NOT A COMPLETE PDF ($size bytes from $host); nothing saved"
    record fallback "download was not a complete PDF ($size bytes)" "" "$size" "$host"
    exit 1
fi
out="$dest/$name.pdf"
n=2
while [ -e "$out" ] && ! cmp -s "$part" "$out"; do
    out="$dest/$name ($n).pdf"; n=$((n+1))
done
cp "$part" "$out"
record fetched "" "$(basename "$out")" "$size" "$host"
echo "task report : $(basename "$out"), $size bytes, complete PDF, from $host -> $out"
echo "route       : browser export (fetched); recorded in $dest/task_report_route.json"
exit 0
