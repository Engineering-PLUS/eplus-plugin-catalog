---
name: contract-document-review
description: Review a folder of submittals and RFIs against the project's own drawings, bulletins and specs, and return stamped PDFs with a review summary.
when_to_use: Use when RFIs or submittals must be reviewed against a project's own Contract Documents sitting in a connected folder (IFC drawing sets, drawing bulletins, a specification set) instead of being looked up one question at a time in the EPLUS knowledge base. Triggers include "review these submittals against the drawings", "review against the contract documents / IFC set / latest bulletins", a folder of submittal packages and drawing sets organized by building, batch review with stamped PDFs and a review summary, and follow-ups on such a review ("you missed the bulletin", "re-review against rev 1", "add this note to every security submittal"). Encodes the review rules, the governing-sheet register built before any analysis, delegation by building, the citation cross-check that runs before packaging, and packaging through the pdf-stamping skill. Cowork only.
argument-hint: <folder or scope, e.g. "review every submittal and RFI in Miner RFI and Submittals">
---

# Contract Document review (folder-based RFIs and submittals)

When invoked as a slash command, apply this workflow to:

$ARGUMENTS

## When this skill applies

| The evidence is... | Use |
|---|---|
| One RFI or a few, answered from the EPLUS knowledge base | the `rfi` skill |
| The project's own drawings, bulletins and specs in a folder, often many items across several buildings | this skill |

Everything in the `rfi` skill about memory (Step 0), the house response format,
client-safe wording, and never citing from pre-training memory still applies
here. What changes:

- **Citations trace to files in the folder.** The knowledge base may be used
  to find a lead, if the user allows it, but a citation names a sheet or spec
  paragraph the review actually read in the project's own documents.
- **No knowledge-base commit during the review.** A batch of draft responses
  is not approved content. When the user later issues responses and wants
  them logged, use the `rfi` skill's return path, one RFI at a time.
- **The research is not delegated to `rfi-researcher`.** That agent only
  reaches the knowledge base. Analysis workers read the folder (Step 3).

## Step 0: one round of questions, then work

Users running a batch review often say they will not be available once
analysis starts. Ask everything in a single round before any analysis (up to
two `AskUserQuestion` calls back to back), skipping anything the user already
stated:

1. **Memory** — the `rfi` skill's Step 0 question, verbatim.
2. **Reviewer name and review date** for the stamp's reviewer cell.
3. **Prior EPLUS review copies** in the folder: fresh review with prior copies
   as reference, fresh review ignoring them, or only unreviewed items.
4. **Knowledge base**: not used, cross-check only, or allowed as a source.
5. **Stamped-copy naming** (house default `EPLUS RESPONSE - <file>.pdf`) and
   **comment colour** (house red unless named).
6. **Stamp decision basis**, if the user did not give one (see Review rules).
7. **Placement when no clean spot exists**: ask per file, or a standing choice
   (smaller scale first, then least-ink corner).

After that round, do not ask again unless the user is plainly still present.
Make the reasonable assumption and record it in the Assumptions and Open
Items Log (Step 5).

## Review rules (defaults; the user's own rules replace them)

**Contract Documents** are the Issued for Construction drawing set for each
building or area, as modified by drawing bulletins; the specification set; and
codes and standards only where a drawing or specification invokes them by
name. When an answer depends on an invoked standard, cite both the invoking
document and the standard's clause.

**Not a basis for a response** unless a Contract Document explicitly
references it: industry practice, manufacturer literature or recommendations,
prior-project precedent, prior review comments.

**Precedence and conflicts:**

- A bulletin supersedes and replaces the sheets it lists. Check the register
  (Step 1) before citing any sheet, and cite the bulletin number and date when
  one governs.
- A drawing and a specification that conflict are not resolved by the
  reviewer. State the conflict, cite both, and recommend elevating it to the
  Engineer of Record.
- Where the Contract Documents are silent, say so and name the closest
  applicable requirement. Never invent one.
- Each item is reviewed against its own building's drawings plus the shared
  specifications. An item filed under one building's folder but titled for
  another is reviewed against the building in its title; record the mismatch.

**Product data:** every submitted item against the equipment schedules and
device lists on the governing sheets (manufacturer, model, ratings, quantities,
options) and against the specification section (performance, listings,
manufacturer requirements, warranty, required submittal content). List
scheduled items missing from the package and packaged items not on the
schedule.

**Shop drawings** are the contractor's interpretation of the contract
drawings: confirm device types, quantities and locations, pathway routing,
conduit and cable sizing, rough-in and mounting heights, and coordination
items the drawings call out. Every deviation gets a sheet or specification
citation.

**Substitution requests:** against the specification's substitution procedure
and required content, then the product itself as product data.

**Disposition basis** (house default; apply only once the user has given or
accepted a basis, otherwise the disposition is the engineer's call per the
`pdf-stamping` skill):

| Stamp | When |
|---|---|
| No Exception | no deviations found |
| Exceptions As Noted | deviations exist and are correctable without resubmittal |
| Rejected (Resubmit) | required content missing, wrong product or building, or deviations that markup cannot resolve |

State the basis for the stamp in the comment block. Apply the same basis to
the same finding across every building; if a worker proposes a different
stamp for a finding already decided elsewhere, the earlier rule wins unless
the facts differ, and the log says why.

**RFI responses** use the `rfi` skill's house format: the answer in the first
sentence, two to four sentences, citations in their own section, any conflict
or gap noted, and a flag when the answer would change the Contract Documents
(potential change order or bulletin).

## Step 1: inventory and the governing-sheet register

Nothing is analyzed until this exists. It is the step that decides whether
the review cites current sheets, and skipping it is how superseded equipment
lists end up in issued comments.

1. **Inventory every document** per building folder: drawing sets, bulletins,
   ASIs, addenda, specification sections, and each RFI and submittal package
   with its revision. Record page counts and file dates.
2. **Find bulletins by content, not file name.** File names are unreliable (a
   misspelled "Bullein" slipped past a name search in the field) and bulletins
   are sometimes filed under a different building's folder. Search every
   folder case-insensitively, then open the first pages of any drawing PDF
   that is not plainly an IFC set and read its title block and revision list.
3. **Write `GOVERNING_SHEETS.md`** in the working folder. Per building:

   | Sheet | Title | Governing document | Date | Replaces |
   |---|---|---|---|---|

   The latest bulletin governs every sheet it re-issues; sheets it does not
   list stay with the IFC set (or the earlier bulletin that last re-issued
   them). Note gaps in bulletin numbering (01 and 04 present, 02 and 03 not)
   as open items.
4. **Never write "no bulletins"** for a building. Write "no bulletin found in
   the folder (searched: <folders and patterns>)". Worker prompts repeat
   exactly what the register says.
5. **Latest revision of every package.** Where a newer revision exists only as
   a cover sheet or tracker entry, review what is present and log that a newer
   revision exists.
6. **Read schedules as images.** Text extraction scrambles tables. For each
   governing equipment list, device schedule or camera matrix a review will
   rely on, render the region and read it, and note in the register that the
   list was confirmed visually.

## Step 2: searchable corpus

One worker extracts every PDF to per-page text (`pages/p0001.txt`) plus low-dpi
page images, with an index per document, so analysis workers grep instead of
opening 600 MB drawing sets. Files that fail to open with `Invalid argument`
on a OneDrive or SharePoint mount are cloud-only placeholders: list them for
the user to download (opening the file once in File Explorer does it) instead
of retrying.

## Step 3: analysis by delegation

- **Write `BRIEFING.md` first**: the review rules above (or the user's), the
  register's location and the rule that every sheet citation names its
  governing document, the house comment format, and the exact return format.
  Every worker reads it before anything else.
- **One worker per building, or per coherent group** (security product data
  for one building, underground shop drawings), never one per file. Use
  `eplus-model-routing:sonnet-standard` when that plugin is installed (the
  full name; the bare `sonnet-standard` does not resolve), otherwise the
  general-purpose agent. Run at most three at once.
- **Each prompt names its governing documents** from the register ("Building B
  IFC set; T00-30 governed by Bulletin 02, 09.03.2026"), the packages by
  folder, and the specification sections that apply.
- **Paths in Cowork:** bash runs in the VM and sees `/sessions/<id>/mnt/...`;
  Read, Write, Edit and Grep run on the Windows host and need the `C:\...`
  path. Tell workers to do corpus work in bash, or give them both forms.
- **Return format**, per item: findings, each with its citation (sheet +
  governing document + date, or specification section and paragraph);
  proposed disposition and its basis; the draft comment block; assumptions;
  documents that could not be read or matched.

## Step 4: lead review, then the cross-check gate

**The main thread owns every word that goes out.** Read each worker's result,
reconcile dispositions across buildings, and write the finalized content to
`FINAL_CONTENT.md`: the single source of truth that every stamp, document and
log is built from. Worker output is never packaged unreviewed.

**Citation cross-check (before any packaging, every time content changes).**
One worker, mechanical, report only. For every comment and response:

1. Extract each sheet number, equipment tag, and manufacturer/model it cites.
2. Sheet: is the cited version the governing one in `GOVERNING_SHEETS.md`?
   A citation of a replaced sheet fails.
3. Tag and model: does the tag exist on the governing list, with that model,
   for that building? Tag numbers are often renumbered between an IFC list
   and its bulletin, so a tag that "exists" may now name a different device.
4. Return a table of every mismatch: item, comment number, what was cited,
   what governs.

Fix the content and re-run until the table is empty, or log each accepted
exception with its reason. Do not stamp or build documents while mismatches
are open.

**Completeness:** every RFI and submittal in the inventory appears in
`FINAL_CONTENT.md`, or is listed as skipped with the reason.

## Step 5: packaging

- **Stamped PDFs:** the `pdf-stamping` skill in batch mode. Build the manifest
  and comment files from `FINAL_CONTENT.md`, run `--plan` over the batch, settle
  unclean placements (Step 0 standing choice or ask), then the real run.
  Originals are never modified. A general note the user supplies goes on its
  own unnumbered line under the header, before comment 1.
- **Word documents:** the docx skill with `eplus-branding`, built
  by a parser script kept in the working folder that reads `FINAL_CONTENT.md`,
  so every revision rebuilds the same way. A general note is not a numbered
  comment and is not counted in comment counts.
- **Assumptions and Open Items Log:** every assumption, every place the
  Contract Documents were silent or conflicting, bulletin gaps, newer
  revisions not provided, and files that could not be read or matched.
- **Verify** with a script or `eplus-model-routing:haiku-fast`: stamped file
  count, each stamped file has one Stamp and one FreeText annotation on the
  stamped page, every item present in the documents. Then render and look at
  a sample of stamped pages and document pages yourself.

## Revisions after delivery

- **Change `FINAL_CONTENT.md` first, then rebuild from it.** Re-stamp from the
  original submittals in batch mode and rebuild the documents. A colour
  change or a new general note is a stamping option and a content edit, never
  a patch applied to already-stamped copies (`pdf-stamping` step 3b).
- **When the user challenges a finding** ("you did not use the latest
  bulletin"), re-run Step 1 for that building, then the cross-check gate for
  the affected items. Report what changed. If the review was right, show the
  governing sheet (rendered image and citation) rather than asserting it.
- **A new revision of a package** gets a page-by-page comparison with the
  previous revision before review, and the response states what changed.

## Filing into a shared document library

Copy only: never move, rename, overwrite, or delete anything in the library.
Survey its folder naming first, place each file in the matching existing
folder, create folders only where none exists using the library's own
pattern, and report every created folder and every judgment call.
