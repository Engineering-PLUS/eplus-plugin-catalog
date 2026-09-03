# Drafting the wording: Steps 3, 3.5, 4 and 5

Covers reading the sources, the wording-review question, drafting every item into
`data/drafted_items.json`, and checking wording against EPLUS precedent. Assumes
`data/items.json` and `build/thumbs_uniform/` exist; `data/drafted_items.json` may not.

### Step 3 — Read every source document, and diff the duplicates

Walk notes frequently arrive as two near-identical files (`…notes.docx` and
`…notes(update).docx`). **Diff them and use the newer one**; call out only real
conflicts. The update usually fixes typos and adds items.

### Step 3.5 — Ask the user how they want the wording set

Once photos are sorted and itemized and BEFORE drafting any item's content,
ask the user with **AskUserQuestion** (one question, three options):

> Photos are sorted into N items. How do you want to set each item's wording?
> 1. **Walk every item with me** — preview each item, I confirm or adjust the
>    wording before it's locked.
> 2. **Review only the ones you're unsure about** — you draft what's clear, I
>    only see the low-confidence items.
> 3. **You draft it** — produce the document; I'll review the finished draft.

"Unsure" in mode 2 means: every `photo_only` and `no_photos` item from the
consolidate triage, anything whose description is inferred from photo content
alone, and anything you would mark `confidence: low`.

**The per-item review loop (modes 1 and 2), order is mandatory:**

1. **Render the preview FIRST, then ask.** Publish an HTML artifact staging the
   item as close as possible to the Word layout — use this skill's
   `templates/item-preview.html` as the reference markup (same fonts, colors,
   two-column photo grid at Word proportions, sheet clip, blank paste-target
   row for photo-less items; photos embedded as data: URIs from the workspace's
   `build/thumbs_uniform/` and `build/sheet_clips_jpg/`). Use ONE artifact and
   republish it for each item (same URL updates in place), so the user watches
   the item change as they answer. Never ask about an item the user cannot
   currently see.
2. **Then ask the item's questions with AskUserQuestion** — proposed
   title/description/corrective action (accept or revise), trade or location
   when ambiguous, and anything the photo inference was unsure of. Ask only
   what is genuinely undecidable from the evidence; don't quiz for its own
   sake.
3. Record each decision into the workspace's `data/drafted_items.json` as you
   go. Wording the user approved or supplied gets `"origin": "user_reviewed"` —
   `build_master.py` treats it as untouchable (no sanitize rewrites, no voice
   guard, no recapitalisation) and FAILS LOUDLY if the text would need
   cleaning, rather than silently altering approved wording.

**Items without photos — always raise it, in every mode.** For each `no_photos`
item, ask (grouped into one AskUserQuestion when there are several):

> Item N has no photos. Options: **(a)** I'll add my own photos in Word — render
> the empty photo grid as a paste target; **(b)** no photos apply — drop the
> grid and the Photos label for this item; **(c)** flag for a follow-up site
> visit — render the empty grid and note it on the issues list.

Record the answer as `"photo_mode": "own_photos" | "none" | "followup"` on the
drafted entry. The renderer honors it: `none` suppresses the photo block
entirely; the other two render one empty grid row sized like a real photo cell
(invisible-hairline rows are a shipped bug this fixed).

### Step 4 — Draft a description for every item

Write into `data/drafted_items.json`, keyed by PlanGrid number.

#### `drafted_items.json` schema

The file is either a bare list of entries, or an object with the entries under
`items` plus an optional `merges` block (see `reference/revising.md`).
`build_master.py` accepts both. One entry per PlanGrid item in scope; an item
with no entry fails the build, so undeterminable items get an entry too.

| Field | Required | Meaning |
|---|---|---|
| `number` | yes | PlanGrid item number (integer). The join key to `items.json`. |
| `title` | yes | Item heading, titled after the observed condition. |
| `description` | yes | Field-report voice. Voice-guarded unless the origin is protected. |
| `corrective_action` | no | Defaults to `N/A, see Editor's Note`. First letter capitalised unless protected. |
| `origin` | yes | Where the wording came from. Free text, but use: `authored` (engineer's own description, polished), `photo_inferred`, `notes_matched`, `undetermined`; **`user_reviewed`** (approved in the Step 3.5 review) and **`reviewer_final`** (recovered from a reviewed .docx) are *protected*: never sanitized, never recapitalised, exempt from the voice guard, and the build fails if `sanitize()` would change them. `review_sheet.py import` writes `reviewer_added` for rows it inserts. |
| `confidence` | yes | `high` / `medium` / `low`, or `reviewer approved` for protected entries. |
| `field_note` | no | The engineer's verbatim pin note. Never rendered; carried to the master as `field_note_original` for the review spreadsheet. |
| `precedent_note` | no | The EPLUS precedent citation, from `get_punch_item`. Rendered inside the Editor's Note box. |
| `editor_note` | no | Internal note to the reviewer. Rendered in the red Editor's Note box, deleted before issuing. Exempt from the voice rules. |
| `photo_mode` | no | For photo-less items: `own_photos` (default, blank paste grid), `none` (no grid, no label), `followup` (blank grid; say why in `editor_note`). |

```json
{
  "items": [
    {
      "number": 14,
      "title": "Conduit Stub-Up at Gridline C",
      "description": "A single conduit is stubbed up through the slab at this location with no box or termination in place. Work remained in progress at the time of the walk.",
      "corrective_action": "Complete the rough-in to the locations identified on the drawings and provide a bushing at the stub.",
      "origin": "photo_inferred",
      "confidence": "medium",
      "field_note": "stub up, no box",
      "precedent_note": "Consistent with NVA02E-118 (open conduit stub, no bushing).",
      "editor_note": "Purpose of the stub is not in evidence; confirm against the floor box plan before issuing.",
      "photo_mode": null
    }
  ],
  "merges": []
}
```

**Items with an authored description:** the engineer's wording is authoritative.
Polish to report voice; never change technical meaning.

**Photo-only items:** check the walk notes first. Then, **before writing one off
as undeterminable, resolve its sheet name and check the other items on the same
sheet.** This is cheap and it works: a photo-only pin showing a boarded-out room
with no visible work looked like a non-finding until its sheet resolved to *MDF-A1
Enlarged Plans*, which made it a specific, defensible finding tied to a still-open
item from an earlier walk.

#### Describe what is present. Never infer what it is for.

The second fabrication mode, and the one the voice rules made *harder* to spot:
once a description is written in confident field-report voice, a wrong inference
reads exactly like a right one.

A v0.1 draft described *"layout markings set out on the slab at the intended
positions, with no floor box rough-in in place."* The markings were for **overhead
hangers**. The photograph showed marks on a slab; everything after that was
invented, and it was invented fluently.

**The rule: state the physical condition, stop before the purpose.**

| Safe, because it is what is there | Unsafe, because it claims to know why |
|---|---|
| "Conduit stubbed up through the slab at this location." | "Floor box rough-in is missing at the positions laid out on the slab." |
| "Layout markings are set out on the slab." | "Layout markings mark the intended floor box positions." |
| "A junction box is mounted to the door jamb stud with cable present." | "The rough-in is consistent with door position hardware." |

On a photo-only pin, **the purpose is precisely the thing not in evidence.** If
the observer's note states the purpose, use the note and say so. If it does not,
describe the condition and let the reviewer supply the intent.

A related trap: do not invent a *category* either. A pin the engineer logged as a
reference photo is not a deficiency, and writing it up as one manufactures a
finding out of a record shot.

**Four outcomes are all valid:**

1. A specific, defensible deficiency.
2. A description qualified by what could not be confirmed.
3. Condition could not be established during the walk; requires field
   verification.
4. **Authored but unverifiable** — a written note with **no photograph** at all.
   This is its own low-confidence category. An authored note is not high
   confidence just because someone typed a sentence; there is nothing to check it
   against. Flag it as such.

**Forcing a confident description onto an ambiguous photo is the single worst
failure mode available here** — it produces a report that reads well and is
partly fiction.

**Title outcome 3 by what is there, not by what is missing.** Headings of the form
*"Wall Rough-In, Subject Not Identified"* were read by a reviewer as *"what does
this mean?"* — the phrase is pipeline jargon leaking onto the page. Title the item
after the observed condition (*"Wall Rough-In at Gridline C"*, *"Conduit Stub-Up,
Location To Be Confirmed"*) and let the description carry the uncertainty.

**Flag, do not describe, pins with no field content at all.** If the only photo
shows a person, a vehicle, an office interior, or a blank wall, the pin is almost
certainly a camera misfire. Surface it as *"should this item be in the report?"*
Do not delete it silently either — that is the human's call.

#### Field-report voice, enforced

The report is written **by** the field engineer, describing the site. Two things
are banned from descriptions, and `build_master.py` fails the build and names the
offending item if either appears:

**1. Narrating the evidence.** "The photograph shows", "visible in the frame",
"not determinable from this photograph". These describe the evidence rather than
the site and make an otherwise solid write-up look machine-produced. State the
condition directly:

> *"Metal stud wall framing at this location carries a junction box with flexible
> metal conduit whips terminating in open air…"*

For genuinely unclear pins, write *"could not be established during the walk and
requires field verification"* — how an engineer would actually say it.

**2. Third-person self-reference.** "The field engineer recorded this condition as
ongoing progress" reads as somebody else narrating the author. Write *"Work
remained in progress at the time of the walk."*

Editor's Notes are internal, are deleted before issuing, and are exempt from both.

**The verbatim pin note is never rendered**, for the same third-person reason. It
stays on the record as `field_note` and appears in the review spreadsheet.

### Step 5 — Check wording against EPLUS precedent

Use the `punch` skill's tools. **Two steps, always:**

1. `query_hermes_punch` to find candidate precedent.
2. **`get_punch_item` to read the exact wording before citing it.** Never quote
   from a search result. The search tool's item bodies are subject to change and
   are already scheduled to be replaced by short snippets; `get_punch_item` is
   the contract for exact wording. Misquoting an engineer's defect wording is not
   a defect the reviewer will catch.

Cap `limit` at 25 yourself — the server does not clamp it, and a large limit
returns tens of thousands of characters.

**On the `trade` filter:** it is exact SQL on every tool, search included, so it
does not silently break. But **trade labels are single-valued and rule-derived**,
and cross-trade defects get exactly one label. A search for *"missing conduit
bushing"* returns hits labelled both `Security` and `Telecom`, because conduit
serving a security device is labelled `Security`. So an empty filtered search
means *"the matching items are labelled under another trade"*, not *"no such
items exist"*. **Drop the `trade` filter first when a filtered search returns
nothing.** On `punch_stats` / `list_punch` / `export_punch_report` the filter
browses the label space directly and has no text intersection to lose, so it is
reliable there.

**Verify the tool is reachable before starting, and say so loudly if it is not.**
A silently-degraded precedent pass produces a finished-looking report whose
wording was never checked, with the caveat buried where nobody reads it.

**Cap yourself at two or three corpus calls at a time.** Each
`query_hermes_punch` returns roughly 6,400 tokens, so eight parallel calls is
~50k tokens in one turn and it compounds across a long drafting session. Batch
small, and prefer `grep_punch` (~780 tokens) and `punch_stats` (~120) wherever
they answer the question. Aim for a citation on every item that can carry one,
and record the coverage in the process log, but get there in small batches.

#### Precedent governs voice, never content

**This is the rule that matters most, and it has already produced a wrong
statement in an issued draft.**

A precedent item shows you *how EPLUS writes a finding*: the sentence shape, the
level of detail, the way a corrective action is addressed. It does **not** tell
you anything about the project in front of you.

The failure, verbatim from a v0.1 review: an item's corrective action read
*"confirm each floor box has rough-in for data back to the serving MDF as
specified."* The phrase came from an **NVA02E** item. At this project the
rough-in does not go back to the MDF. The sentence was well formed, correctly
voiced, and factually invented, and nothing downstream could catch it because it
reads exactly like a real finding.

So:

- **Never carry a project-specific noun across from a precedent item.** Room
  names, device names, MDF/IDF references, routing, panel numbers, mounting
  heights. If it names a thing, it has to come from *this* project's notes,
  drawings, or photos.
- **Write corrective actions to point at the drawings rather than restate them.**
  *"and required rough-in to the locations identified on the drawings"* is right.
  *"back to the serving MDF as specified"* is a claim about a system you have not
  seen.
- **When precedent and the observer's note disagree, the observer wins.** The
  engineer walked the site. The corpus did not.

Before an item ships, every specific noun in its description and corrective
action should trace to this project's source data. If it traces only to a
precedent citation, cut it or generalise it.

**Known corpus gap:** the corpus is entirely interior fit-out. Underground duct
bank, vault and hand hole work returns nothing. Items of that kind have **no
precedent basis** — write the corrective action from the contractual requirement
and state the gap in the item's Editor's Note rather than hiding it. Do not
invent wording to fill the space.


Next: `reference/render.md` (assemble the master JSON and render the .docx).
