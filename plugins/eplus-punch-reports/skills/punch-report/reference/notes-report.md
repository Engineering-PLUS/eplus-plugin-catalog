# A report from notes and photos, no PlanGrid

For a walk that never went into PlanGrid: the engineer has site photos and
notes, in a Word or text file in the project folder, in uploads, or typed in
chat ("write up my notes from today's walk at POR03C"). There is no pull,
no Task Report and no drawing, so the item pages carry **Location** and
**Date Recorded** and no sheet-clip column. The cover, the TOC, the
letterhead, the voice rules, the finish list and the delivery are the same as
any other report.

The rule from `run-order.md` still holds: build first, ask last. Nothing
below waits on the user.

## 1. Workspace and inputs

```bash
python3 "$S/scripts/locate_inputs.py" "<what the user typed>"     # route: photos and notes
bash "$S/scripts/init_workspace.sh" <workspace>
cd <workspace>/_pipeline && bash scripts/install_deps.sh
```

Copy the photos into `<workspace>/site_photos/` and the notes file beside
`_pipeline/`, once. iPhone `.heic` photos do not open in the sandbox: list
them in the finish list rather than converting them by hand.

## 2. The items: one file, written by you

Read the notes and look at the photos. Write `data/notes_items.json`, one
entry per deficiency, **in the order the notes give them**:

```json
{"items": [
  {"title": "Missing Cable Labels",
   "location": "IDF-POR03C, cabinet 1:6",
   "date": "2026-10-22",
   "description": "Horizontal cabling is missing barrel labels at both ends.",
   "corrective_action": "Contractor to provide matching labels on both ends.",
   "photos": ["IMG_0412.jpg", "IMG_0413.jpg"]}
]}
```

- **The notes are the engineer's words.** Polish them into field-report voice
  (`reference/drafting.md`, the voice rules and the title style), never add a
  condition the notes and photos do not show. A note too thin to write up
  still gets an item, with an `editor_note` saying what is missing.
- **Photos to items is inference.** Match by what the photo shows and by file
  order or time; a photo you cannot place goes on no item and into the finish
  list. An item with no photo gets an empty paste row (leave `photos` empty).
- **Location** is whatever the notes say (room, cabinet, grid line); leave it
  empty rather than guess. **Date** is the walk date from the notes or the
  photos' dates; empty if neither says.
- Precedent (`drafting.md` Step 5) applies as usual when the punch-history
  tools are loaded.

## 3. Build and render

```bash
python3 scripts/notes_to_items.py data/notes_items.json --photos ../site_photos
python3 scripts/prefill_config.py --project-name "<project as the user named it>" --version <next> \
    [--project-folder <project folder>]
RENDER_ONLY=1 bash scripts/run_pipeline.sh
```

`notes_to_items.py` writes `data/items.json` and `data/drafted_items.json`,
copies the photos to `../notes_photos/` (the package carries them),
normalises them, and sets `"sheet_clips": false`. A project name in the EPLUS
form `CLIENT - BUILDING - EP no` fills the cover's client, building and EP
number; otherwise they show `[MISSING: ...]` and the finish list asks.

## 4. Paperwork, questions, delivery

As `run-order.md` sections 6 to 8: the paperwork, the draft and the finish
list, one `AskUserQuestion` for the blocking gaps, the answers in one
`update_report.py` call, then `package.py` once. A change after delivery is
`update_report.py`, as for any report.

Next: `reference/run-order.md`, section 6.
