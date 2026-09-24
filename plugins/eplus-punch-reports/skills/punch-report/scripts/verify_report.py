#!/usr/bin/env python3
"""
verify_report.py, check the rendered .docx without converting it to PDF.

Verification used to run by converting to PDF with LibreOffice and scanning the
text layer. That is no longer done, for two reasons:

  1. We do not produce the PDF any more. The reviewer generates it from Word
     when the markup is finished, so Word recalculates fields on export.
  2. LibreOffice paginates differently from Word, so any check that depended on
     its pagination was measuring the wrong renderer. That is exactly what made
     the old static TOC page numbers wrong.

So these checks read the OOXML directly, which is what Word will actually open.
Anything genuinely pagination dependent cannot be asserted here and is instead
handled by making Word compute it (PAGEREF fields + w:updateFields).

What the letterhead check covers, and what it does not: it asserts that a
header part contains a table, the two letterhead images (EP logo and URL), the
"Technology System" / "Punch List" text and the shaded divider paragraph, and
that no header consists of a lone drawing. It does NOT measure image widths,
check the header's position against the body margins, verify which image files
were embedded, or inspect the footer. Those are what render_preview.py is for.

Usage:
    python3 verify_report.py build/<Project>-Punch-Report-DRAFT-v0.1.docx
"""
import json
import os
import re
import sys
import zipfile

DASH_RE = re.compile(r"[–—]")
# One list, owned by build_master.py, so a description the build accepted can
# never fail here. The fallback only matters if the script is run alone.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from build_master import VOICE_BANNED
except Exception:  # pragma: no cover
    VOICE_BANNED = [r"\b(photo(graph)?s?|images?)\s+(show|depict|capture)", r"\bthis photo",
                    r"\bin the frame", r"\bfield engineer"]


USAGE = ("usage: verify_report.py <report.docx> [master_report_items.json]\n"
         "\n"
         "Checks the rendered .docx by reading its OOXML directly. No LibreOffice\n"
         "and no PDF conversion: verification must read the artifact the reader\n"
         "actually opens, and LibreOffice paginates differently from Word.\n"
         "\n"
         "  report.docx                the rendered report\n"
         "  master_report_items.json   defaults to alongside the .docx\n")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(USAGE)
        sys.exit(0 if len(sys.argv) > 1 else 2)
    path = sys.argv[1]
    master_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(path) or ".", "master_report_items.json")

    z = zipfile.ZipFile(path)
    doc = z.read("word/document.xml").decode("utf8")
    settings = z.read("word/settings.xml").decode("utf8")
    master = json.load(open(master_path, encoding="utf-8"))
    n_items = len(master)

    # report.config.json carries some INTERNAL fields that must never reach the
    # client-facing document. Absent config just skips those checks.
    cfg_path = os.path.join(os.path.dirname(master_path) or ".", "report.config.json")
    cfg = {}
    if os.path.isfile(cfg_path):
        try:
            cfg = json.load(open(cfg_path, encoding="utf8"))
        except Exception:
            cfg = {}

    # visible text only, so XML attributes cannot create false positives
    text = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", doc))
    norm = re.sub(r"\s+", " ", text)

    # Visit sections, derived exactly as gen_report.js derives them, so the
    # expected TOC entry count includes them.
    visit_titles = []
    if isinstance(cfg.get("visit_breaks"), list) and cfg["visit_breaks"]:
        visit_titles = [b.get("title") or f"Site Visit {i + 1}" for i, b in enumerate(cfg["visit_breaks"])]
    elif cfg.get("visit_sections") == "by_date":
        last, n = object(), 0
        for m in master:
            d = m.get("date_recorded")
            if d != last:
                n += 1
                visit_titles.append(f"Site Visit {n}, {d or 'date not recorded'}")
                last = d
        if len(visit_titles) < 2:
            visit_titles = []
    n_visits = len(visit_titles)

    pagerefs = re.findall(r"PAGEREF\s+(\w+)", doc)
    bookmarks = set(re.findall(r'w:bookmarkStart[^>]*w:name="((?:punchitem|visit)\d+)"', doc))
    media = [n for n in z.namelist() if n.startswith("word/media/")]
    expected_photos = sum(len(m["photo_paths"]) for m in master)

    checks = []

    # Date Recorded comes from the pin, so it is never N/A on an item whose pin
    # carries a date. Field result 2026-09-14: photo-derived dates left 27 of 38
    # items reading N/A and cost a second delivery.
    # Blank fill-in pages (blank_template.py) have no pin and no date by design.
    undated = [m["plangrid_ref"] for m in master if not m.get("date_recorded") and not m.get("blank")]
    n_na = norm.count("Date Recorded N/A")
    checks.append(("Date Recorded populated from the pin date", n_na <= len(undated),
                   f"{n_na} item(s) read 'Date Recorded N/A' but only {len(undated)} lack a pin date "
                   f"{undated}; rebuild the master (build_master.py writes date_recorded)"))
    if undated:
        checks.append(("every item carries a pin date (created_at)", False,
                       f"missing on {undated}; the pull's created_at did not reach items.json"))

    # Deleted pins kept (deleted_pins keep) are bannered, one banner per pin, and
    # nothing else is.
    n_deleted = sum(1 for m in master if m.get("deleted_in_plangrid"))
    n_banner = norm.count("DELETED IN PLANGRID.")
    checks.append((f"deleted-in-PlanGrid banner on {n_deleted} retained pin(s), no others",
                   n_banner == n_deleted, f"{n_banner} banner(s) in the body"))

    # Visit section titles appear in the body when configured.
    for t in visit_titles:
        checks.append((f"visit section present: {t}", t in norm, "title not found in the body text"))

    # content integrity
    checks.append(("no em or en dashes", not DASH_RE.findall(text),
                   f"{len(DASH_RE.findall(text))} found"))
    # Voice rule applies to DESCRIPTIONS ONLY. Editor's Notes are internal, are
    # deleted before issuing, and legitimately talk about photos and pins, so
    # scanning the whole document text produces false failures.
    voice_hits = []
    for m in master:
        # Human-approved wording is exempt here exactly as in build_master.py;
        # update_report.py marks every user edit user_reviewed, so without this
        # the verifier could fail a sentence the build already accepted.
        if m.get("origin") in ("reviewer_final", "user_reviewed"):
            continue
        for pat in VOICE_BANNED:
            hit = re.search(pat, m["description"], re.I)
            if hit:
                voice_hits.append(f"{m['plangrid_ref']}:{hit.group(0)}")
    checks.append(("no photo narration or third person in descriptions", not voice_hits,
                   f"matched {voice_hits}"))
    checks.append(("verbatim pin note not rendered", "original note" not in text, "found"))

    # docx@9.7.1's ImportedXmlComponent.fromXmlString() (used for the TOC field's
    # fldChar/instrText runs) returns a wrapper node with no element name for the
    # top-level xml2js document node; convertToXmlComponent()'s `case void 0:`
    # treats that wrapper as real and emits a literal <undefined>...</undefined>
    # tag around the fragment. Every lax parser (including LibreOffice) accepts
    # the well-formed-but-undeclared tag; Word does not, and refuses to open the
    # file. gen_report.js's importXml() helper unwraps .root[0] to avoid this;
    # this check asserts none slipped through.
    illegal_tags = re.findall(r"</?undefined\b", doc)
    checks.append(("no schema-illegal element names (e.g. <undefined>)",
                   not illegal_tags,
                   f"found {len(illegal_tags)} <undefined> tag(s) in word/document.xml"))

    # TOC must be live fields, not baked text. One entry per item plus one per
    # visit section heading (they are Heading 1 too, so Word lists them).
    n_toc = n_items + n_visits
    checks.append((f"{n_toc} PAGEREF fields present ({n_items} items"
                   + (f" + {n_visits} visit sections)" if n_visits else ")"),
                   len(pagerefs) == n_toc, f"got {len(pagerefs)}"))
    checks.append(("every PAGEREF resolves to a bookmark",
                   not (set(pagerefs) - bookmarks),
                   f"dangling: {sorted(set(pagerefs) - bookmarks)}"))
    # Names being right is NOT enough. The docx library writes every bookmark
    # with w:id="1", and Word keys bookmarks on the numeric id, not the name:
    # duplicate ids mean it keeps one and discards the rest, so every TOC entry
    # after the first renders "Error! Bookmark not defined." on F9. That shipped
    # once. fix_bookmark_ids.py renumbers them; this asserts it ran.
    bm_ids = re.findall(r'<w:bookmarkStart[^>]*w:id="(\d+)"', doc)
    dup_ids = sorted({i for i in bm_ids if bm_ids.count(i) > 1})
    checks.append(("bookmark ids are unique", not dup_ids,
                   f"duplicated w:id {dup_ids}, run scripts/fix_bookmark_ids.py"))
    # Same failure mode, different element: docx@9.7.1's DocProperties builds a
    # fresh docPropertiesUniqueNumericIdGen() per instance when no explicit id is
    # passed, so every wp:docPr (one per embedded image) gets id="1" by default.
    # Word keys on this id the same way it keys on bookmark ids; duplicates are a
    # corruption trigger. gen_report.js's imageRun() helper shares one counter
    # across the document so each docPr gets a distinct id; this asserts it did.
    docpr_ids = []
    for tag in re.findall(r"<wp:docPr\b[^>]*/?>", doc):
        m = re.search(r'id="(\d+)"', tag)
        if m:
            docpr_ids.append(m.group(1))
    dup_docpr = sorted({i for i in docpr_ids if docpr_ids.count(i) > 1})
    checks.append(("wp:docPr ids are unique", not dup_docpr,
                   f"duplicated wp:docPr id {dup_docpr} ({len(docpr_ids)} docPr elements total)"))
    checks.append(("no stale hardcoded page numbers",
                   not re.findall(r">p\. \d+<", doc), "found baked 'p. N' text"))
    checks.append(("Word set to refresh fields on open",
                   "<w:updateFields" in settings, "w:updateFields missing"))

    # The contents block must be a REAL TOC field (begin / instr / separate /
    # cached entries / end), not free-standing paragraphs: only a field makes
    # Word's Update Table repair titles, numbers AND entry count together.
    # Checked in the form Word actually consumes, not by trusting the renderer.
    toc_instrs = re.findall(r"<w:instrText[^>]*>([^<]*TOC[^<]*)</w:instrText>", doc)
    checks.append(("a TOC field instruction is present", len(toc_instrs) == 1,
                   f"found {len(toc_instrs)} TOC instrText nodes, expected 1"))
    if toc_instrs:
        canonical = re.match(r"^ TOC \\o &quot;1-1&quot; \\h \\z \\u $", toc_instrs[0]) \
            or re.match(r'^ TOC \\o "1-1" \\h \\z \\u $', toc_instrs[0])
        checks.append(("TOC instruction is canonical", bool(canonical),
                       f"got {toc_instrs[0]!r}"))
        # The field must open before the first cached entry and close after the
        # last: an unterminated field swallows the rest of the document on F9.
        toc_pos = doc.find(toc_instrs[0])
        seg = doc[:toc_pos]
        begins = seg.count('w:fldCharType="begin"')
        after = doc[toc_pos:]
        checks.append(("TOC field opens and closes",
                       begins >= 1 and 'w:fldCharType="separate"' in after
                       and 'w:fldCharType="end"' in after,
                       "field chars incomplete around TOC instruction"))
    checks.append((f"TOC cached entries match item count ({n_toc})",
                   len(pagerefs) == n_toc,
                   f"{len(pagerefs)} entries against {n_toc} headings; the TOC has rotted, "
                   "re-render (or Update Table in Word on a hand-edited copy)"))

    # layout. An item that opens a visit section takes its page break from the
    # section title paragraph, so the count is per item either way.
    checks.append(("one page break per item",
                   doc.count("<w:pageBreakBefore/>") >= n_items,
                   f"got {doc.count('<w:pageBreakBefore/>')}"))
    checks.append(("all photos embedded", len(media) >= expected_photos,
                   f"{len(media)} media vs {expected_photos} photos"))

    # Letterhead must be native, not a pasted strip. The renderer builds it as a
    # two-column table in the header (EP logo + URL images left, "Technology
    # System" / "Punch List" text right) followed by a shaded divider paragraph.
    # A pasted bitmap is a header holding one lone drawing and no table. Media
    # file names carry no information (docx names them image1.jpg, image2.png,
    # ...), so the check reads the header parts themselves. It does NOT measure
    # widths or placement; see the module docstring.
    header_parts = [n for n in z.namelist() if re.match(r"word/header\d*\.xml$", n)]
    native_found, lone_bitmap = False, []
    for n in header_parts:
        hx = z.read(n).decode("utf8")
        htext = " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", hx))
        n_draw = hx.count("<w:drawing>")
        has_tbl = "<w:tbl>" in hx
        if (has_tbl and n_draw >= 2 and "Technology System" in htext
                and "Punch List" in htext and 'w:fill="44546A"' in hx):
            native_found = True
        if n_draw >= 1 and not has_tbl:
            lone_bitmap.append(n)
    checks.append(("letterhead built natively (header table, 2 images, title text, divider)",
                   native_found and not lone_bitmap,
                   f"header parts {header_parts}: native={native_found}, "
                   f"lone drawing without a table in {lone_bitmap}"))

    # The EP project number belongs on the cover (the issued coversheet leads
    # with it) and nowhere else. The body is verified here; the cover file, when
    # one was written, is verified below.
    ep_no = str(cfg.get("ep_project_no") or "").strip()
    if ep_no and not ep_no.startswith("<"):
        checks.append(("EP project number not in the body (cover only)",
                       ep_no not in norm,
                       f"'{ep_no}' appears in the body text"))

    # Page 1 of the body is blank in every cover_mode but "none": its own section
    # with no header reference of its own, so the reviewer's coversheet swap keeps
    # the numbering right. Checked as the first sectPr carrying no headerReference
    # to the letterhead part.
    cover_mode = cfg.get("cover_mode") or ("none" if cfg.get("include_cover") is False else "template")
    sect_count = doc.count("<w:sectPr")
    if cover_mode != "none":
        checks.append(("body page 1 is a blank section (cover swapped in later)",
                       sect_count >= 2, f"{sect_count} section(s); expected a blank first section"))

    # The cover is a separate file in "template" mode: <output>-Cover.docx beside
    # the body. Same two Word-only defects can bite it, and its content must
    # carry what the issued coversheet carries.
    cover_path = re.sub(r"\.docx$", "-Cover.docx", path, flags=re.I)
    if cover_mode == "template" and os.path.isfile(cover_path):
        cz = zipfile.ZipFile(cover_path)
        cdoc = cz.read("word/document.xml").decode("utf8")
        ctext = re.sub(r"\s+", " ", " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", cdoc)))
        cids = [m.group(1) for m in re.finditer(r'<wp:docPr\b[^>]*id="(\d+)"', cdoc)]
        checks.append(("cover: no schema-illegal element names", "<undefined" not in cdoc, "found <undefined>"))
        checks.append(("cover: wp:docPr ids are unique", len(cids) == len(set(cids)), f"{cids}"))
        checks.append(("cover: one page, no letterhead header",
                       cdoc.count("<w:sectPr") == 1 and not any(re.match(r"word/header\d*\.xml$", n) for n in cz.namelist()),
                       "cover should be a single section with no header parts"))
        if ep_no and not ep_no.startswith("<"):
            checks.append(("cover: EP project number present", ep_no in ctext, f"'{ep_no}' missing from the cover"))
        sub = str(cfg.get("cover_subtitle") or "").strip()
        if sub and not sub.startswith("<"):
            checks.append(("cover: building / subtitle present", sub in ctext, f"'{sub}' missing"))
        # Every walk date in the pull is on the cover: a two-day walk shows both
        # (inspection_date may be a list). Field result 2026-09-14: the cover
        # said 08/27/2026 for a walk that ran 08/27 and 08/28.
        pin_dates = sorted({m.get("date_recorded") for m in master if m.get("date_recorded")})
        missing_dates = [d for d in pin_dates if d not in ctext]
        checks.append((f"cover: inspection date covers every pin date ({', '.join(pin_dates) or 'none'})",
                       not missing_dates,
                       f"{missing_dates} not on the cover; set inspection_date to the list of walk dates"))
        # The issuance date is asked, never inferred, and "TBD" is the sanctioned
        # placeholder on a draft; the inspection date must still be a real date.
        n_dates = len(re.findall(r"\b\d{2}/\d{2}/\d{4}\b", ctext))
        # With no pins there is no walk date to take (an empty or blank-template
        # report): a red [MISSING: walk date] stands in for it and the finish list
        # asks for it. Field result 2026-09-24: an empty report failed here, which
        # stopped the run before the review sheet and the finish list.
        walk = 1 if (not pin_dates and "[MISSING: walk date]" in ctext) else 0
        iss = str(cfg.get("issuance_date") or "").strip().upper()
        if iss in ("", "TBD") or iss.startswith("<"):
            checks.append(("cover: inspection date in MM/DD/YYYY, issuance date TBD",
                           n_dates + walk >= 1 and "TBD" in ctext.upper(),
                           f"{n_dates} date(s) found; expected the inspection date and a visible TBD"))
        else:
            checks.append(("cover: dates in MM/DD/YYYY", n_dates + walk >= 2,
                           "expected inspection and issuance dates as MM/DD/YYYY"))
        checks.append(("cover: no draft warning on the cover", "DRAFT" not in ctext.upper() or "FOR INTERNAL REVIEW" not in ctext.upper(),
                       "the draft block belongs in the first Editor's Note, not on the cover"))
        # Template hint text ("<Client and project as it reads ...>") must never
        # reach the cover; an unknown fact renders as a red [MISSING: ...] marker.
        checks.append(("cover: no template placeholder text", "&lt;" not in ctext and "<" not in ctext,
                       "a '<...>' template hint is on the cover; set the field or leave it empty"))
        n_missing = ctext.count("[MISSING:")
        checks.append((f"cover: {n_missing} field(s) marked MISSING (listed in the finish list)", True, ""))
    elif cover_mode == "template":
        checks.append(("cover file written beside the body", False, f"{os.path.basename(cover_path)} not found"))

    print(f"verifying {os.path.basename(path)}  ({n_items} items)\n")
    failed = 0
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  <- {detail}"))
        failed += not ok

    print(f"\n  embedded media: {len(media)}  |  file size: {os.path.getsize(path)/1e6:.1f} MB")
    print("\n  NOTE: page numbers are Word fields. They are blank or stale until Word")
    print("  updates them, which it does on open and on PDF export. Ctrl+A then F9 forces it.")

    if failed:
        sys.exit(f"\n{failed} check(s) FAILED")
    print("\nall checks passed")


if __name__ == "__main__":
    main()
