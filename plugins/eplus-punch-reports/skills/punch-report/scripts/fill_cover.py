#!/usr/bin/env python3
"""
fill_cover.py -- write <report>-Cover.docx from one of EPLUS's own coversheets.

Run from _pipeline/ (run_pipeline.sh calls it after the body render):

    python3 scripts/fill_cover.py [build]          # reads build/report.config.json
    python3 scripts/fill_cover.py --list           # the templates and what each matches

The covers are the coversheets EPLUS issues, shipped as Word files in
_pipeline/covers/ (refreshed from the plugin by init_workspace.sh on every
run). They are used as they are: the artwork, the logos and the layout are
the designer's, and this script only replaces the text of the fields below.
Field result 2026-10-22 and earlier: the cover drawn from code never matched
the issued sheet and carried no client logo, so reviewers rebuilt it by hand.

  <name>.docx    the coversheet, set in Arial
  <name>.json    which client it is for ("match": words looked for in the
                 client name and the PlanGrid project name) and the sample
                 text of each field as it reads in the .docx, so the field
                 can be found and replaced

Which cover: report.config.json "cover_template" names one; otherwise the
first whose "match" word appears in client_display_name or cover_title;
otherwise default.docx (the same sheet with no client logo).

Fields and where their text comes from (report.config.json):
  eyebrow        cover_eyebrow        (the line above the white rule)
  building       cover_subtitle       (large, under the rule)
  client_line    client_display_name  (bottom right; the template's
                                       "client_line" pattern may add the building)
  address_1/2    site_address         (a list of lines, or one string split at
                                       its first comma)
  EP Project No, Inspection Date, Issuance Date, Inspector
                 ep_project_no, inspection_date, issuance_date, inspector
                 (found by their labels; dates print MM/DD/YYYY)

A fact nobody has supplied prints as a red "[MISSING: ...]" marker, as on the
body. Anything else on a cover (a different logo, a one-off wording) is edited
in Word by the reviewer; a new client gets its own <name>.docx and <name>.json
in the plugin's covers/ folder.
"""
import argparse
import json
import os
import re
import sys
import zipfile
from datetime import date
from xml.sax.saxutils import escape, unescape

LABELS = {
    "EP Project No:": "ep_project_no",
    "Inspection Date:": "inspection_date",
    "Issuance Date:": "issuance_date",
    "Inspector:": "inspector",
}
MISSING_LABELS = {
    "building": "building or area", "client_line": "client name", "address_1": "site address",
    "ep_project_no": "EP project number", "inspection_date": "walk date", "inspector": "inspector",
}
ALERT_RED = "B00000"  # the body's Editor's Note red (gen_report.js)
# an innermost paragraph: no other <w:p> opens inside it (<w:pPr> is not a paragraph)
PARA = re.compile(r"<w:p[ >](?:(?!<w:p[ >]).)*?</w:p>", re.S)
RUN = re.compile(r"<w:r(?: [^>]*)?>.*?</w:r>", re.S)
TEXT = re.compile(r"<w:t(?: [^>]*)?>([^<]*)</w:t>")


def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def is_missing(v):
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip() or v.strip().startswith("<")
    if isinstance(v, list):
        return not v or all(is_missing(x) for x in v)
    return False


def fmt_date(v):
    if isinstance(v, list):
        return " & ".join(d for d in (fmt_date(x) for x in v) if d)
    s = re.sub(r"^Site walk:\s*", "", str(v or ""), flags=re.I).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m:
        return f"{m.group(2)}/{m.group(3)}/{m.group(1)}"
    return s


def address_lines(v):
    if is_missing(v):
        return []
    lines = [str(x).strip() for x in v if not is_missing(x)] if isinstance(v, list) else [str(v).strip()]
    if len(lines) == 1 and "," in lines[0]:
        # "4735 Northeast Starr Boulevard, Hillsboro, Oregon" -> street, then city and state
        s = lines[0]
        lines = [s[:s.index(",") + 1], s[s.index(",") + 1:].strip()]
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    return lines


def para_text(p):
    return unescape("".join(TEXT.findall(p)))


def first_rpr(run):
    m = re.search(r"<w:rPr>.*?</w:rPr>", run, re.S)
    return m.group(0) if m else "<w:rPr></w:rPr>"


def alert(rpr):
    """The run properties of a [MISSING] marker: bold, red. CT_RPr is ordered: b before color before sz."""
    rpr = re.sub(r"<w:b\s*/>|<w:b w:val=\"[^\"]*\"\s*/>", "", rpr)
    rpr = re.sub(r"<w:color [^>]*/>", "", rpr)
    m = re.search(r"<w:rFonts [^>]*/>|<w:rStyle [^>]*/>", rpr)
    at = m.end() if m else len("<w:rPr>")
    rpr = rpr[:at] + "<w:b/>" + rpr[at:]
    m = re.search(r"<w:(?:spacing|w|kern|position|sz|szCs|highlight|u|effect|bdr|shd|fitText|vertAlign|rtl|cs|em|lang|eastAsianLayout|specVanish|oMath) |</w:rPr>", rpr)
    return rpr[:m.start()] + f'<w:color w:val="{ALERT_RED}"/>' + rpr[m.start():]


def value_run(rpr, text):
    if text.startswith("[MISSING:"):
        rpr = alert(rpr)
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def rewrite(p, text, keep_label=False):
    """The paragraph with its runs replaced by one run of `text` (after the label runs, if kept)."""
    runs = list(RUN.finditer(p))
    if not runs:
        return p
    head = p[:runs[0].start()]
    head = re.sub(r"<w:proofErr [^>]*/>", "", head)
    label, value_rpr, acc = "", None, ""
    for r in runs:
        t = unescape("".join(TEXT.findall(r.group(0))))
        if keep_label and value_rpr is None and (not acc.rstrip().endswith(":") or not t.strip()):
            label += r.group(0)
            acc += t
            continue
        value_rpr = first_rpr(r.group(0))
        break
    if value_rpr is None:
        # a label with no value run: the value takes the label's look without the bold
        value_rpr = re.sub(r"<w:b\s*/>|<w:bCs\s*/>", "", first_rpr(runs[0].group(0)))
    return head + (label if keep_label else "") + value_run(value_rpr, text) + "</w:p>"


def pick_template(cfg, covers):
    names = sorted(f[:-5] for f in os.listdir(covers) if f.endswith(".docx") and not f.startswith("~$"))
    want = str(cfg.get("cover_template") or "").strip()
    if want:
        want = os.path.splitext(os.path.basename(want))[0]
        if want not in names:
            sys.exit(f"ERROR: cover_template '{want}' not in {covers} (have: {', '.join(names)})")
        return want
    hay = " ".join(str(cfg.get(k) or "") for k in ("client_display_name", "cover_title")).lower()
    for n in names:
        for word in (load(os.path.join(covers, n + ".json"), {}) or {}).get("match", []):
            if re.search(r"\b" + re.escape(word.lower()) + r"\b", hay):
                return n
    return "default"


def values(cfg, spec):
    def val(key, label):
        v = cfg.get(key)
        return f"[MISSING: {label}]" if is_missing(v) else None

    building = "" if is_missing(cfg.get("cover_subtitle")) else str(cfg["cover_subtitle"]).strip()
    client = "" if is_missing(cfg.get("client_display_name")) else str(cfg["client_display_name"]).strip()
    if client:
        pattern = spec.get("client_line", "{client}")
        # "{client} {building}" on the Stack sheet; never twice when the name already carries it
        line = client if (building and building.lower() in client.lower()) else pattern.format(client=client, building=building)
        client_line = re.sub(r"\s+", " ", line).strip()
    else:
        client_line = f"[MISSING: {MISSING_LABELS['client_line']}]"
    addr = address_lines(cfg.get("site_address"))
    out = {
        "eyebrow": str(cfg.get("cover_eyebrow") or "Technology Site Inspection"),
        "building": building or f"[MISSING: {MISSING_LABELS['building']}]",
        "client_line": client_line,
        "address_1": addr[0] if addr else f"[MISSING: {MISSING_LABELS['address_1']}]",
        "address_2": addr[1] if len(addr) > 1 else "",
        "ep_project_no": val("ep_project_no", "EP project number") or str(cfg["ep_project_no"]).strip(),
        "inspection_date": (f"[MISSING: {MISSING_LABELS['inspection_date']}]"
                            if is_missing(cfg.get("inspection_date") or cfg.get("walk_date"))
                            else fmt_date(cfg.get("inspection_date") or cfg.get("walk_date"))),
        "issuance_date": "TBD" if is_missing(cfg.get("issuance_date")) else fmt_date(cfg["issuance_date"]),
        "inspector": val("inspector", "inspector") or str(cfg["inspector"]).strip(),
    }
    return out


def fill(xml, spec, vals):
    by_sample = {re.sub(r"\s+", " ", s).strip(): f for f, s in (spec.get("fields") or {}).items()}
    hits = {}

    def sub(m):
        p = m.group(0)
        t = re.sub(r"\s+", " ", para_text(p)).strip()
        if not t:
            return p
        for label, key in LABELS.items():
            if t.startswith(label):
                hits[key] = hits.get(key, 0) + 1
                return rewrite(p, vals[key], keep_label=True)
        field = by_sample.get(t)
        if field:
            hits[field] = hits.get(field, 0) + 1
            return rewrite(p, vals[field])
        return p

    return PARA.sub(sub, xml), hits


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("build", nargs="?", default="build")
    ap.add_argument("--covers", default=None, help="cover templates folder (default: _pipeline/covers)")
    ap.add_argument("--list", action="store_true", help="list the cover templates and what each matches")
    args = ap.parse_args()

    pipe = os.path.dirname(os.path.abspath(args.build))
    covers = args.covers or os.path.join(pipe, "covers")
    if not os.path.isdir(covers):
        sys.exit(f"ERROR: {covers} not found; re-run init_workspace.sh from the plugin to refresh it")
    if args.list:
        for f in sorted(os.listdir(covers)):
            if f.endswith(".docx"):
                spec = load(os.path.join(covers, f[:-5] + ".json"), {}) or {}
                print(f"{f:<16} matches: {', '.join(spec.get('match', [])) or '(fallback)'}  {spec.get('about', '')}")
        return 0

    cfg = load(os.path.join(args.build, "report.config.json"))
    if cfg is None:
        sys.exit(f"ERROR: {args.build}/report.config.json not found")
    mode = cfg.get("cover_mode") or ("none" if cfg.get("include_cover") is False else "template")
    if mode != "template":
        print(f"cover        : not written (cover_mode {mode})")
        return 0

    name = pick_template(cfg, covers)
    spec = load(os.path.join(covers, name + ".json"), {}) or {}
    vals = values(cfg, spec)
    out = os.path.join(args.build, re.sub(r"\.docx$", "", cfg["output_filename"], flags=re.I) + "-Cover.docx")
    tmp = out + ".part"
    hits = {}
    with zipfile.ZipFile(os.path.join(covers, name + ".docx")) as zin, \
            zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "word/document.xml":
                xml, hits = fill(data.decode("utf-8"), spec, vals)
                data = xml.encode("utf-8")
            zout.writestr(zipfile.ZipInfo(info.filename, info.date_time), data, zipfile.ZIP_DEFLATED)
    os.replace(tmp, out)

    # Every field the template declares must have been found: a template edited
    # in Word so its sample text no longer matches would otherwise ship the old
    # project's facts silently.
    wanted = set((spec.get("fields") or {}).keys()) | set(LABELS.values())
    lost = sorted(wanted - set(hits))
    print(f"cover        : {os.path.basename(out)}  (template {name}.docx, {date.today().isoformat()})")
    for k in ("eyebrow", "building", "client_line", "address_1", "address_2",
              "ep_project_no", "inspection_date", "issuance_date", "inspector"):
        if k in wanted:
            print(f"  {k:<16}: {vals[k]}")
    if lost:
        print(f"ERROR: field(s) not found in {name}.docx: {', '.join(lost)}. The sample text in {name}.json "
              f"no longer matches the document; fix the .json (plugin covers/ folder).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
