# Verify, keep editable, deliver: Steps 8, 9 and 10

Covers OOXML and visual verification, the two human-edit paths (Word comments, review
spreadsheet), and the single delivery to the project folder. Assumes a rendered `.docx`
exists in `build/`; the issues list and handoff files may still need filling in.

### Step 8 — Verify against the OOXML

`verify_report.py` reads the .docx XML directly — no LibreOffice dependency —
because verification must read the artifact the reader actually opens. It checks
em/en dashes, the voice rules (**scoped to descriptions only**, since Editor's
Notes legitimately discuss photographs), PAGEREF/bookmark integrity including
**unique bookmark ids**, a single **canonical TOC field** that opens and closes
around a cached entry list matching the item count, absence of baked page
numbers, `w:updateFields`, page breaks per item, embedded photo count, the
internal EP project number being absent, and that the letterhead is native: a
header part holding the two-column table, both letterhead images, the
"Technology System / Punch List" text and the shaded divider, with no header
consisting of a lone drawing. The letterhead check does **not** measure image
widths or placement against the margins; that is what the visual check below is
for.

**When writing OOXML text assertions, normalise whitespace first.** Joining
`<w:t>` runs doubles spaces, which produces phantom failures on exact matches.

Anything genuinely pagination-dependent is not asserted; it is delegated to Word
by using fields.

**Visual verification closes the gap OOXML checks can't.** An element existing
in the XML does not mean the page looks right — the empty photo grid once
shipped verified only by a `<w:tc>` cell count, which cannot distinguish a
visible paste target from a collapsed hairline row. For layout changes, run

```bash
python3 scripts/render_preview.py build/<output>.docx --pages 1,4
```

It rasterises to PNG via a scratch-dir PDF **which it deletes** — no PDF
survives to be mistaken for a deliverable (the PDF-block hook exempts this
script by name). It needs a `soffice` binary on PATH; **whether the Cowork
sandbox ships one is unverified** — if it does not, the script says so and the
OOXML checks stand alone. Rule: **layout and appearance may be checked in the
preview; anything numeric must be checked in the OOXML** — the preview's
pagination is LibreOffice's, not Word's, so never quote a page number from it.
The one thing neither can prove is Word's own F9 behavior; after any
template-level TOC change, do the manual acceptance test once: delete an item
in Word, Ctrl+A F9, confirm the TOC loses the entry and renumbers.

### Step 9 — Keep the report editable by a human

A rendered .docx is a compiled artifact. Without care the only thing that can
revise it is another model run — a trap, because reports get edited by whoever is
holding them at 5pm. Two escape hatches, both must keep working.

**Small edits: directly in Word.** Item headings use **Word's own numbering**, not
text like `Item #7`. Delete an item and the rest renumber. Do not "fix" this by
writing the number into the heading text.

The PlanGrid ID is deliberately **not** in the heading, and as of v0.7 it is **not
rendered anywhere the contractor sees** — that meta row was removed. It is retained
in `master_report_items.json` as `plangrid_ref` and shown in the review
spreadsheet, which is where anyone reconciling against PlanGrid reads it. The
printed number is presentational and will change; the PlanGrid ref is the
permanent link back to source and is never renumbered.

**Reviewer comments in Word: read them back.** Reviewers comment directly in the
.docx, and a comment the model cannot see is a comment that gets ignored.

```bash
python3 scripts/read_comments.py <reviewed>.docx            # readable
python3 scripts/read_comments.py <reviewed>.docx --json -o comments.json
```

Each comment comes back **with the text it is anchored to and the item heading it
falls under**, because "reword this" is meaningless without the span it points at.
Resolved comments are hidden unless you pass `--include-resolved`. Replies are
linked to their parent.

Work the comments before re-rendering, and treat a comment that says "see comment
above" as applying to every instance of the same pattern, not just its own item.

**Bulk edits: the review spreadsheet.**

```bash
python3 scripts/review_sheet.py export build -o Report-Review.xlsx
#   reviewer edits the yellow columns
python3 scripts/review_sheet.py import build Report-Review.xlsx
node scripts/gen_report.js build
```

Yellow cells editable, grey generated and ignored on import, so photo paths and
sheet clips cannot be corrupted by editing the sheet. `Include? = N` drops an
item, `Order` (spaced by 10) reorders, a row with no PlanGrid ref inserts one. A
timestamped `.bak.json` is written before anything changes.

### Step 10 — Deliver the draft, the issues list, and the handoff

Three deliverables, not one, and they leave the workspace together in one
package:

```bash
python3 scripts/package.py <workspace> "<project folder>"
```

That zips the whole workspace (pipeline, sources, data, build, handoff, minus
`node_modules` and caches) into the project folder and places the `.docx` and
the review `.xlsx` beside it. It is the only write to the project folder in the
entire run, it refuses to overwrite a previous delivery, and `--dry-run` shows
the manifest first. Do not copy files across by hand before or after it.

**The issues list** (`_pipeline/ISSUES-LIST.md`) is first-class. It carries source
conflicts (report both, never silently pick one), items referencing documents you
were not given, suspected misfires as questions, items where the photo contradicts
the description, multi-condition pins for a split/keep decision, everything
drafted from photos rather than authored, authored-but-photoless items, and any
pattern that belongs above item level. Call out the few that genuinely block
issuance.

**The handoff** (`_pipeline/PROCESS-LOG.md`, `LESSONS-LEARNED.md`,
`handoff/HANDOFF.md`) is how the next run gets better than this one. Fill these in
as you go. Write down what broke, the root cause rather than the symptom, and
whether the fix is enforced in code or only written down — a rule that is only
written down will be broken again.

**Write the process log from what the code does, not what it should do.** The
previous package documented four behaviours its code did not have, and each cost
real time later.


Next: `reference/revising.md` when the reviewer returns the document or a further round is asked for.
