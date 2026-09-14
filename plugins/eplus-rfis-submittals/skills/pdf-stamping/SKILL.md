---
name: pdf-stamping
description: Apply EPLUS Bluebeam review stamps and the EPLUS comment block to submittal PDFs, producing an "EPLUS RESPONSE - " copy with live, Bluebeam-editable annotations. Use whenever the user asks to stamp a submittal, add a DRAFT or FOR REFERENCE ONLY watermark, apply "Exceptions As Noted" / "No Exception" / "Rejected (Resubmit)" / "Review Required" / "For Record" / "For Information Only", add the ENGINEERING PLUS COMMENTS box to a drawing, change the comment colour or add a general note on already-stamped copies, stamp a batch of submittals, or mark a submittal reviewed. Cowork-only — it needs PyMuPDF and a real filesystem. Handles Bluebeam annotation stamps, which a plain PDF merge silently fails to render.
---

# EPLUS submittal stamping

Produces a stamped **reference copy** of a submittal: the firm's review stamp,
the ENGINEERING PLUS COMMENTS box beneath it (house red unless the user names
another colour), and optionally a DRAFT watermark on every page.

## Scope and status

- **Cowork only.** The script needs PyMuPDF and local file access. In a chat
  session with no filesystem, say so and stop — do not describe the stamp in
  prose as a substitute.
- **The output is a reference copy, not an issued document.** The reviewer
  opens it in Bluebeam, adjusts, and issues. Everything this skill writes is a
  **live annotation** so it stays editable there.
- Proven on Letter-size submittals. Landscape, rotated, and scanned sheets are
  untested — flag that rather than assuming.

## Setup

The Cowork VM runs **Python 3.10** at `/usr/bin/python3` and needs the
`--break-system-packages` flag:

```bash
python3 -m pip install "pymupdf>=1.25" --break-system-packages
```

`stamp_pdf.py` checks Python and PyMuPDF capabilities on startup and prints the
fix if either is too old — run it once before promising the user an output.
Nothing else is required: no numpy, no poppler.

`scripts/` and `stamps/` ship with the skill. `stamp_pdf.py` finds the bundled
stamps on its own (`../stamps` relative to the script); pass `--stamps-dir`
only when the user points somewhere else.

## Which stamp

Two classes, and they are not interchangeable. The script refuses to swap them.

| Class | Names | Applied to |
|---|---|---|
| **Review stamp** (`--stamp`) | Exceptions As Noted · No Exception · Rejected (Resubmit) · Review Required · For Record · For Information Only | one page |
| **Watermark** (`--watermark`) | Draft · For Reference Only | every page |

Ask which review stamp if the user hasn't said. Do not infer a disposition from
the review comments — that is the engineer's call, and it is the one thing on
the page a contractor acts on. The one exception: in a document-set review
(`document-review` skill) where the user has stated a decision basis — which
findings earn No Exception, Exceptions As Noted, or Rejected (Resubmit) — apply
that basis and write it into the comment block, so the engineer can see why.

## Inputs to establish first

- **Source PDF** — the submittal.
- **Review stamp** — ask if not stated.
- **Comments** — the ENGINEERING PLUS COMMENTS list, if there is one.
- **Comment colour** — house red (`FF0000`) unless the user names another.
  Pass it as `--comment-color <hex>`; it colours the comment text and border
  only, never the review stamp. A name like "light violet" is not a colour
  value: pick the hex, say which one you picked, and use it for every file.
- **Watermark** — usually `Draft`, when the copy is for internal reference.
  Do **not** reach for `--watermark-opacity` to lighten it: the stamp file
  already carries its own transparency (Draft is 40% grey) and the flag
  compounds with it. Leave it at the default 1.0 unless the user wants it
  lighter than the stamp as authored.
- **Reviewer name** — fills the `&[User]` cell. **Required**; the script aborts
  rather than shipping a raw `&[User]` token. Ask; do not assume it is the stamp owner.
- **Date** — fills `&[Date]`, defaults to today, `MM/DD/YYYY`.
- **Which page** the review stamp goes on. Usually the first sheet of actual
  content, which is often not page 1.

## Procedure

### 1. Write the comments to a file

One line per numbered comment, opening with the header line:

```
ENGINEERING PLUS COMMENTS:
1. EC shall confirm ...
2. Contractor to provide ...
```

Use `--comments-file`. It keeps quoting and line breaks intact, which inline
`--comments` does not.

A standing note that applies to the whole submittal (a basis-of-review or
GENERAL NOTE the user supplies) goes on its own unnumbered line directly under
the header, before comment 1. It is part of the block, not a numbered comment:

```
ENGINEERING PLUS COMMENTS:
GENERAL NOTE: This submittal is reviewed solely for ...
1. EC shall confirm ...
```

### 2. Plan the placement before writing anything

```bash
python3 scripts/stamp_pdf.py "<submittal>.pdf" \
    --stamp "Exceptions As Noted" --stamp-page 3 \
    --comments-file comments.txt --plan
```

`--plan` writes nothing. It reports the block size and ranked candidate
placements, each with `clean` (sits entirely on blank paper) and
`covers_ink_pct`.

**If `clean_placement_exists` is true**, take the best clean candidate and go.
Prefer the house placement — `auto-blank:top`, which reproduces the top-left
position of the issued example — unless a different clean candidate is
obviously better for the sheet.

**If no candidate is clean, stop and ask the user.** Do not pick for them and
do not quietly cover their drawing. Present the real options with
`AskUserQuestion`, using the numbers from the plan:

1. **A different page** — often the cleanest fix; the block may fit on the
   cover sheet or a following sheet.
2. **A smaller block** — `--stamp-scale 0.85` or `0.7`; say what the plan
   reports for coverage at that scale.
3. **Cover content at the least-damaging spot** — name the corner and the
   `covers_ink_pct` from the plan. This needs `--allow-overlap`.
4. **White background over content** — `--comment-fill white` with
   `--allow-overlap`. This *hides* whatever is underneath the comment box.
   **Last resort.** Say plainly what it will obscure.

Never pass `--allow-overlap` until the user has chosen one of these.

### 3. Apply

```bash
python3 scripts/stamp_pdf.py "<submittal>.pdf" \
    --watermark "Draft" \
    --stamp "Exceptions As Noted" --stamp-page 3 --stamp-fit auto \
    --comments-file comments.txt \
    --reviewer "<reviewer>" --date MM/DD/YYYY
```

Output is `EPLUS RESPONSE - <submittal>.pdf` next to the original. When the
user asks for a different naming convention, pass `--out` with the full path.

### 3a. Several submittals: batch mode

More than two or three files go through one `--batch` run, not a loop of
single calls. One process loads each stamp once, and the run writes a JSON
line per job as it finishes, so a shell timeout part-way through still leaves
a record of what completed.

```json
{
  "defaults": {"reviewer": "<reviewer>", "date": "MM/DD/YYYY",
               "comment-color": "FF0000"},
  "jobs": [
    {"input": "A/sub-001.pdf", "stamp": "Rejected (Resubmit)",
     "comments-file": "comments/001.txt", "out": "A/sub-001 - EPLUS.pdf"},
    {"input": "B/sub-014.pdf", "stamp": "Exceptions As Noted", "stamp-page": 2,
     "comments-file": "comments/014.txt", "out": "B/sub-014 - EPLUS.pdf"}
  ]
}
```

- Any single-file option works as a job or `defaults` key, with hyphens or
  underscores. Precedence: job, then `defaults`, then the command line. An
  unknown key fails that job by name, so a typo cannot silently fall back to a
  default.
- Relative paths resolve against the manifest's folder.
- `--batch manifest.json --plan` plans every job and writes nothing. Run it
  first; any job whose plan has no clean candidate goes back to the user
  exactly as in step 2, and gets its chosen `stamp-fit` / `stamp-scale` /
  `allow-overlap` in the manifest before the real run.
- A job that cannot be placed fails with its candidates in the result line;
  the other jobs still run. The exit code is 1 if any job failed.
- Large packages take a while to save. If the shell tool has a short timeout,
  run the batch in the background with its output redirected to a log file,
  then read the log. If a run is cut off, re-run with `--skip-existing` to
  pick up where it stopped.

### 3b. Changing issued comments (colour, a new note, revised text)

Re-stamp from the **original** submittal with the updated comments file and
options. Never patch colours or text inside an already-stamped copy with an
ad-hoc script: the colour lives in five places in the annotation (see
LESSONS-LEARNED section 12), and a partial patch leaves a box that renders one
way here and another way when someone edits it in Bluebeam. Replacing an
existing stamped copy means deleting it first — ask before deleting.

### 4. Verify visually — every time, no exceptions

```bash
python3 -c "import pymupdf,sys; d=pymupdf.open(sys.argv[1]); \
d[int(sys.argv[2])-1].get_pixmap(dpi=110).save('check.png')" \
"EPLUS RESPONSE - <submittal>.pdf" 3
```

Then **look at `check.png`** and confirm, explicitly:

- the review stamp is actually there and is not squashed or stretched;
- the reviewer/date cell shows real values, not `&[User] &[Date]`;
- the comment box sits directly under the stamp at the same width, and no
  comment line is cut off at the bottom border;
- the stamp and box do not cover anything the user needs to read.

A PDF that saves without error is **not** evidence the stamp rendered — these
are annotation stamps and the naive approach fails silently. Any warning the
script prints on stderr is a real finding; relay it.

### 5. Report

Give the output path, the stamp and watermark applied, the page, the reviewer
and date, and where the block landed. If anything was covered, say what.

## Rules

- Never overwrite or modify the original submittal. The script refuses, but do
  not work around it.
- Never edit the files in `stamps/` — they are the firm's controlled documents.
  If a stamp needs changing, say so and let the stamp owner change it in Bluebeam.
- Never ship a file that still shows `&[User]` or `&[Date]`.
- Never choose the disposition stamp yourself, and never invent comment text —
  the comments come from the engineer or from an approved RFI response.
- The watermark goes on before the review stamp so the stamp can never land on
  top of it. Do not reorder the operations.

## Not covered

- Yellow `EPLUS:` point callouts on interior pages — add those in Bluebeam.
- Different review stamps on different pages of one submittal in one pass
  (batch mode stamps many submittals, one review stamp each).

## Reference

- `reference/LESSONS-LEARNED.md` — why `bake()` is required, the measured house
  geometry, the three PyMuPDF traps, and the open questions. Read it before
  changing `scripts/stamp_pdf.py`.
- `scripts/inspect_stamp.py` — structure dump for any stamp PDF. Run it first
  whenever a new stamp is added to `stamps/`; it reports the class, whether the
  artwork is raster or vector, the token fields, and the ink bbox.
- `scripts/stamp_pdf.py` — `load_stamp()`, `ink_bbox()`, `InkMap`,
  `find_blank()`, `plan_placement()`, `add_stamp_annot()`, and
  `add_comment_box()` are importable if a task needs something the CLI doesn't
  cover.
