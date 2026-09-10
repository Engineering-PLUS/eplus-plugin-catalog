#!/usr/bin/env python3
"""
fetch_photos.py -- download the original site photos for an MCP pull.

The plangrid MCP's get_task tool returns each photo as a signed URL. This
script downloads every URL listed in <pull>/mcp_photo_urls.json into
<pull>/photos/<uid>__<title>.jpg, which is the name consolidate.py indexes on.

Run this FIRST, every run, before falling back to the Task Report PDF. The
originals are full resolution; the copies embedded in the Task Report PDF are
about 350 x 620 px and get upscaled in the rendered document. Whether a host
is reachable is a property of the seat on the day, not of the project, so do
not skip this step because a previous run, a memory note, or a prior package's
CLAUDE.md says the host was blocked.

    python3 scripts/fetch_photos.py --pull ../plangrid_mcp

Prints one summary line per outcome and always exits 0. If any photo failed,
the last line says so and names the fallback:

    python3 scripts/extract_pdf_photos.py "../<Task Report>.pdf" --pull ../plangrid_mcp

mcp_photo_urls.json shape, as written from get_task results:
    {"<task number>": [{"uid": ..., "title": ..., "created_at": ..., "url": ...}, ...], ...}
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

EGRESS_HINT = ("blocked by the network allowlist (egress). File it with "
               "request_egress_allow per the error-reporting skill, then use the PDF route.")


def fetch(url, dest, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": "eplus-punch-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pull", default="../plangrid_mcp",
                    help="folder holding mcp_photo_urls.json; photos/ is created inside it")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    args = ap.parse_args()

    pull = os.path.abspath(args.pull)
    meta_path = os.path.join(pull, "mcp_photo_urls.json")
    if not os.path.isfile(meta_path):
        print(f"ERROR: {meta_path} not found; write it from the get_task results first", file=sys.stderr)
        return 1
    meta = json.load(open(meta_path, encoding="utf-8"))
    dest = os.path.join(pull, "photos")
    os.makedirs(dest, exist_ok=True)

    total = ok = skipped = 0
    failed = []
    hosts_failed = set()
    for num, photos in meta.items():
        for p in photos:
            total += 1
            url = p.get("url")
            uid, title = p.get("uid"), p.get("title") or p.get("uid")
            if not url or not uid:
                failed.append((num, uid, "no url in metadata"))
                continue
            out = os.path.join(dest, f"{uid}__{title}.jpg")
            if os.path.exists(out) and os.path.getsize(out) > 0 and not args.force:
                skipped += 1
                continue
            try:
                fetch(url, out, args.timeout)
                if os.path.getsize(out) == 0:
                    raise IOError("empty response")
                ok += 1
            except Exception as e:  # noqa: BLE001 - any failure is a per-photo failure
                if os.path.exists(out):
                    os.remove(out)
                reason = str(e).splitlines()[0][:120] if str(e) else type(e).__name__
                failed.append((num, uid, reason))
                hosts_failed.add(url.split("/")[2] if "//" in url else url)

    print(f"photos listed     : {total}")
    print(f"downloaded        : {ok} -> {dest}")
    if skipped:
        print(f"already present   : {skipped}")
    if failed:
        print(f"failed            : {len(failed)}")
        for num, uid, reason in failed[:20]:
            print(f"   item {num} {uid}: {reason}")
        if any("403" in r or "Forbidden" in r or "CONNECT" in r for _, _, r in failed):
            print(f"hosts {sorted(hosts_failed)} look {EGRESS_HINT}")
        print("route             : FALLBACK NEEDED. Run scripts/extract_pdf_photos.py against the "
              "Task Report PDF for the missing photos, and record 'pdf' as the photo route in "
              "PROCESS-LOG.md.")
    else:
        print("route             : live (original resolution). Record 'live' as the photo route.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
