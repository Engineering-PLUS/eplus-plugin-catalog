#!/usr/bin/env python3
"""
task_report_to_pull.py -- build the pull from a PlanGrid Task Report PDF alone.

For a run with no PlanGrid connector (not connected, signed out, failing) and
a Task Report PDF in the project folder or uploads. The PDF carries every
field the report needs: the task number and title, status, description,
created date and author, sheet number, and each photo with its caption. It is
a complete input, not a fallback to ask about. Field result 2026-10-22: the
connector was down, a Task Report was in the folder, and the run stopped to
tell the user to relaunch the app; when told to carry on it wrote this
converter in scratch.

    python3 scripts/task_report_to_pull.py "../<Task Report>.pdf"            # -> ../plangrid_mcp
    python3 scripts/task_report_to_pull.py "../<Task Report>.pdf" --out ../plangrid_mcp

Then the normal MCP-route steps, unchanged:

    python3 scripts/extract_pdf_photos.py "../<Task Report>.pdf" --pull ../plangrid_mcp
    python3 scripts/adapt_mcp_pull.py
    bash scripts/run_pipeline.sh

Writes, in --out:
  tasks.json    {"coverage": {"source": "task_report_pdf", ...}, "tasks": [rows]}, rows in
                the plangrid MCP's get_tasks shape (uid, number, title, status,
                description, created_at, updated_at, created_by, sheet, photos)
  project.json  the report header: PlanGrid project name and site address,
                which prefill_config.py reads for the cover

--header-only writes project.json alone. run_pipeline.sh runs it on the MCP
route, where the connector supplies the tasks but not the project address
(list_projects carries none), so the address still comes from the header.

What the PDF does not carry: sheet titles (only the number prints), photo
originals (the photos are embedded at about 350 x 620 px), and the PlanGrid
uids (synthetic ones are made: pdftask-<N>, pdfphoto-<N>-<k>). A later run
with the connector working replaces all three.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

try:
    import pymupdf as fitz
except ImportError:  # older PyMuPDF
    import fitz

LABELS = ("Status", "Type", "Created", "Last Updated", "Sheet", "Description", "Photos",
          "Assigned To", "Assignee", "Due Date", "Room", "Location", "Manager", "Root Cause",
          "Cost Impact", "Schedule Impact", "Watchers")
TITLE_RE = re.compile(r"^#(\d+)\s+(.*)$")
DATE_RE = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4} \d{1,2}:\d{2} [AP]M$")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# header lines that are never the project address
NOT_ADDRESS_RE = re.compile(r"^(?:Prepared by\b|Created with\b|PlanGrid\b|Page \d|\d+(?: of \d+)?$"
                            r"|[A-Z][a-z]{2} \d{1,2}, \d{4}\b)", re.I)


def iso(s):
    """Oct 22, 2026 9:05 AM -> 2026-10-22T09:05:00 (local time, as the PDF prints it)."""
    try:
        return datetime.strptime(s.strip(), "%b %d, %Y %I:%M %p").strftime("%Y-%m-%dT%H:%M:00")
    except ValueError:
        return None


def blocks(page):
    """Text blocks as (x0, y0, x1, y1, [lines]), header and footer bands removed."""
    h = page.rect.height
    out = []
    for b in page.get_text("blocks"):
        if b[6] != 0:
            continue
        lines = [ln.strip() for ln in b[4].splitlines() if ln.strip()]
        if not lines or b[1] < 0.075 * h or b[1] > 0.94 * h:
            continue
        out.append((b[0], b[1], b[2], b[3], lines))
    return out


def header(doc):
    """(project name, address) from the running header the item pages repeat:
    the most common top-band text across pages (the title page may differ).
    A project with no address in PlanGrid prints "Prepared by <name>" and the page
    number under the name (field result 2026-10-29: Project Miner - Operations),
    and neither is an address."""
    seen = Counter()
    for page in doc:
        h = page.rect.height
        top = sorted((b for b in page.get_text("blocks") if b[6] == 0 and b[1] < 0.075 * h),
                     key=lambda b: b[1])
        lines = [ln.strip() for b in top for ln in b[4].splitlines()
                 if ln.strip() and not NOT_ADDRESS_RE.match(ln.strip())]
        if lines:
            seen[tuple(lines[:2])] += 1
    if not seen:
        return "", ""
    lines = max(seen, key=lambda k: (seen[k], len(k)))
    return lines[0], (lines[1] if len(lines) > 1 else "")


def labelled(bl):
    """{label: (block, value lines)} for the blocks that open with a field label."""
    out = {}
    for b in bl:
        if b[4][0] in LABELS and b[4][0] not in out:
            out[b[4][0]] = (b, b[4][1:])
    return out


def captions(bl):
    """Photo captions on a page: three one-line blocks stacked (title, author, date),
    in reading order (rows within 60pt, then left to right)."""
    one = sorted(((b[0], b[1], b[4][0]) for b in bl if len(b[4]) == 1), key=lambda z: (round(z[0]), z[1]))
    caps, used = [], set()
    for i in range(len(one) - 2):
        a, n, d = one[i], one[i + 1], one[i + 2]
        if i in used or not DATE_RE.match(d[2]) or DATE_RE.match(a[2]):
            continue
        if abs(a[0] - n[0]) < 3 and abs(a[0] - d[0]) < 3 and 0 < d[1] - a[1] < 30:
            caps.append((a[0], a[1], a[2], n[2], d[2]))
            used.update((i, i + 1, i + 2))
    caps.sort(key=lambda c: c[1])
    rows = []
    for c in caps:
        if rows and abs(c[1] - rows[-1][0][1]) < 60:
            rows[-1].append(c)
        else:
            rows.append([c])
    return [c for r in rows for c in sorted(r)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pdf")
    ap.add_argument("--out", default="../plangrid_mcp", help="raw pull folder (default ../plangrid_mcp)")
    ap.add_argument("--header-only", action="store_true",
                    help="write project.json only (the MCP route: the tasks come from the connector)")
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    project, address = header(doc)
    if args.header_only:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "project.json"), "w", encoding="utf-8") as f:
            json.dump({"name": project, "address": address, "source": "task_report_pdf"}, f, indent=1)
        print(f"project      : {project or '(no header)'}")
        print(f"address      : {address or '(none in the header)'}")
        return 0
    tasks, cur = [], None
    for pno, page in enumerate(doc):
        bl = blocks(page)
        title = next((TITLE_RE.match(ln) for b in bl for ln in b[4]
                      if TITLE_RE.match(ln) and "...." not in ln), None)
        fields = labelled(bl)
        if title and "Status" in fields:
            num = int(title.group(1))
            cur = {"uid": f"pdftask-{num}", "number": num, "title": title.group(2).strip(),
                   "deleted": False, "photos": [], "page": pno + 1}
            tasks.append(cur)
            val = lambda k: " ".join(fields[k][1]).strip() if k in fields else ""
            cur["status"] = val("Status").lower()
            cur["type"] = val("Type")
            created = fields.get("Created", (None, []))[1]
            cur["created_at"] = iso(created[0]) if created else None
            # an e-mail address wraps across lines in the PDF ("...@eplusadvisor" / "s.com")
            em = EMAIL_RE.search("".join(created[1:]))
            cur["created_by"] = em.group(0) if em else ""
            upd = fields.get("Last Updated", (None, []))[1]
            cur["updated_at"] = iso(upd[0]) if upd else None
            sheet = val("Sheet")
            cur["sheet"] = {"uid": f"pdfsheet-{sheet}", "name": sheet} if sheet else None
            cur["sheet_uid"] = cur["sheet"]["uid"] if sheet else None
            # the description runs on in further blocks of the same column, down to Photos
            desc = ""
            if "Description" in fields:
                db, lines = fields["Description"]
                stop = fields["Photos"][0][1] if "Photos" in fields else page.rect.height
                more = [b for b in bl if b is not db and abs(b[0] - db[0]) < 5 and db[1] < b[1] < stop
                        and b[4][0] not in LABELS]
                desc = " ".join(lines + [ln for b in sorted(more, key=lambda b: b[1]) for ln in b[4]])
            cur["description"] = re.sub(r"\s+", " ", desc).strip()
        elif cur is None:
            continue  # the title page and the contents
        # captions on the item page and on its continuation pages, in order
        for _x, _y, ptitle, author, when in captions(bl):
            k = len(cur["photos"]) + 1
            cur["photos"].append({"uid": f"pdfphoto-{cur['number']}-{k}", "title": ptitle,
                                  "created_by": author, "created_at": iso(when)})

    for t in tasks:
        t["photos_count"] = len(t["photos"])
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "tasks.json"), "w", encoding="utf-8") as f:
        json.dump({"coverage": {"source": "task_report_pdf", "pdf": os.path.basename(args.pdf),
                                "tasks": len(tasks)}, "tasks": tasks}, f, indent=1)
    with open(os.path.join(args.out, "project.json"), "w", encoding="utf-8") as f:
        json.dump({"name": project, "address": address, "source": "task_report_pdf"}, f, indent=1)

    print(f"project      : {project or '(no header)'}")
    print(f"address      : {address or '(none in the header)'}")
    print(f"tasks        : {len(tasks)} -> {os.path.join(args.out, 'tasks.json')}")
    for t in tasks:
        print(f"  #{t['number']:<5} {t['status']:<8} {(t['created_at'] or '?')[:10]}  {(t['sheet'] or {}).get('name', '-'):<12}"
              f" {t['photos_count']} photo(s)  {t['title'][:40]}")
    nodesc = [t["number"] for t in tasks if not t["description"]]
    if nodesc:
        print(f"no description: {nodesc}")
    if not tasks:
        print("ERROR: no task pages found; is this a PlanGrid Task Report?", file=sys.stderr)
        return 1
    print("next         : extract_pdf_photos.py, then adapt_mcp_pull.py, then run_pipeline.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
