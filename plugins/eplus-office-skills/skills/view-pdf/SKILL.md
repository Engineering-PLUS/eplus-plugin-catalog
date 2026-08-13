---
name: view-pdf
description: Interactive PDF viewer. Use when the user wants to open, show, or view a PDF and collaborate on it visually — annotate, highlight, stamp, fill form fields, place signature/initials, or review markup together. Not for summarization or text extraction (use native Read instead).
---

# PDF Viewer — Interactive Document Workflows

You have access to a local PDF server that renders documents in a live
viewer and lets you annotate, fill forms, and place signatures with
real-time visual feedback.

## When to use this skill

**Use the PDF viewer when the user wants interactivity:**
- "Show me this contract" / "Open this paper"
- "Highlight the key terms and let me review"
- "Help me fill out this form"
- "Sign this on page 3" / "Add my initials to each page"
- "Stamp this CONFIDENTIAL" / "Mark this as approved"
- "Walk me through this document and annotate the important parts"

**Do NOT use the viewer for pure ingestion:**
- "Summarize this PDF" → use the native Read tool directly
- "What does page 5 say?" → use Read
- "Extract the table from section 3" → use Read

The viewer's value is showing the user the document and collaborating
on markup — not streaming text back to you.

## Tools

### `list_pdfs`
List available local PDFs and allowed local directories. No arguments.

### `display_pdf`
Open a PDF in the interactive viewer. **Call once per document.**
- `url` — local file path or HTTPS URL
- `page` — initial page (optional, default 1)
- `elicit_form_inputs` — if `true`, prompts the user to fill form
  fields before displaying (use for interactive form-filling)

Returns a `viewUUID` — pass this to every `interact` call. Calling
`display_pdf` again creates a **separate** viewer; interact calls with
the new UUID won't reach the one the user is looking at.

Also returns `formFields` (name, type, page, bounding box) if the PDF
has fillable fields — use these coordinates for signature placement.

### `interact`
All follow-up actions after `display_pdf`. Pass `viewUUID` plus one or
more commands. **Batch multiple commands in one call** via the
`commands` array — they run sequentially. End batches with
`get_screenshot` to verify changes visually.

**Annotation actions:**
- `add_annotations` — add markup (see types below)
- `update_annotations` — modify existing (id + type required)
- `remove_annotations` — delete by id array
- `highlight_text` — auto-find text by query and highlight it
  (preferred over manual rects for text markup)

**Navigation actions:**
- `navigate` (page), `search` (query), `find` (query, silent),
  `search_navigate` (matchIndex), `zoom` (scale 0.5–3.0)

**Extraction actions:**
- `get_text` — extract text from page ranges (max 20 pages). Use for
  reading content to decide what to annotate, NOT for summarization.
- `get_screenshot` — capture a page as an image (verify your annotations)

**Form action:**
- `fill_form` — fill named fields: `fields: [{name, value}, ...]`

## Annotation Types

All annotations need `id` (unique string), `type`, `page` (1-indexed).
Coordinates are PDF points (1/72 inch), origin **top-left**, Y increases
downward. US Letter is 612×792pt.

| Type | Key properties | Use for |
|------|----------------|---------|
| `highlight` | `rects`, `color?`, `content?` | Mark important text |
| `underline` | `rects`, `color?` | Emphasize terms |
| `strikethrough` | `rects`, `color?` | Mark deletions |
| `note` | `x`, `y`, `content`, `color?` | Sticky-note comments |
| `freetext` | `x`, `y`, `content`, `fontSize?` | Visible text on page |
| `rectangle` | `x`, `y`, `width`, `height`, `color?`, `fillColor?` | Box regions |
| `circle` | `x`, `y`, `width`, `height`, `color?`, `fillColor?` | Circle regions |
| `line` | `x1`, `y1`, `x2`, `y2`, `color?` | Draw lines/arrows |
| `stamp` | `x`, `y`, `label`, `color?`, `rotation?` | APPROVED, DRAFT, CONFIDENTIAL, etc. |
| `image` | `imageUrl`, `x?`, `y?`, `width?`, `height?` | **Signatures, initials**, logos |

**Image annotations** accept a local file path or HTTPS URL (no data:
URIs). Dimensions auto-detected if omitted. Users can also drag & drop
images directly onto the viewer.

## Interactive Workflows

### Opening a document
1. If the user gives a path or URL, `display_pdf` it directly. If not,
   call `list_pdfs` first to show what's available.
2. After displaying, offer next steps based on the document type:
   - **Contract / report** → "Want me to highlight key sections or add
     review notes?"
   - **Form** → "This has fillable fields — shall I help you fill it?"
   - **Academic paper** → "Shall I walk through and annotate the key
     findings?"

### Collaborative annotation (AI-driven default)
1. `display_pdf` to open the document (or reuse an existing `viewUUID`)
2. `interact` → `get_text` on relevant page range (≤20 pages) to
   understand content
3. Propose a batch of annotations to the user, describing what you'll
   mark, e.g.: "I'll highlight the termination clause on page 2, add a
   note 'Review 30-day window' next to it, and stamp page 1 as DRAFT.
   Sound good?"
4. On approval, `interact` → `add_annotations` + `get_screenshot` of
   the affected page
5. Show the user, ask for edits, iterate on the next section
6. When done, remind them they can download the annotated PDF from the
   viewer toolbar

**Manual mode:** if the user gives explicit instructions ("highlight
paragraph 3", "stamp CONFIDENTIAL on every page"), skip the proposal
step and execute directly — still confirm with a screenshot.

**Tips:** prefer `highlight_text` over manual `rects` for text markup;
batch related annotations in one `interact` call; keep proposals small
(3–5 annotations per batch) so review is easy.

### Form filling (visual, not programmatic)
Unlike headless form tools, this gives the user **live visual
feedback** on every field as it's filled, with easy undo/edit in the
viewer, and handles forms with cryptic/unnamed fields where the label
is printed on the page rather than in field metadata (e.g. a W-9 with
field names like `f1_1`, `f1_2`, `c1_1` — use `get_screenshot` to match
each bounding box to its printed label before asking the user or
filling from context).

1. `display_pdf` — inspect returned `formFields` (name, type, page,
   bounding box)
2. If field names are cryptic (`Text1`, `Field_7`), `get_screenshot`
   the pages and match bounding boxes to visual labels
3. Ask the user for values using the **visual** labels, or infer from
   context
4. `interact` → `fill_form`, then `get_screenshot` to show the result
5. User confirms or edits directly in the viewer

For simple well-labeled forms, `display_pdf` with
`elicit_form_inputs: true` prompts the user upfront instead.

Signature fields are usually separate — fill text fields first, then
move to the signing workflow below for the image.

### Signing (visual, not certified)
1. Ask for the signature/initials image path (PNG/JPG). If they don't
   have one, suggest they create one and save it to a known path.
2. `display_pdf` (or reuse an existing `viewUUID`); check `formFields`
   for signature-type fields, or ask which page/position — e.g. a
   typical bottom-right signature on US Letter is around `x: 400,
   y: 700`.
3. `interact` → `add_annotations` with `type: "image"` at the target
   coordinates, e.g. `{"id": "sig1", "type": "image", "page": 3,
   "imageUrl": "/path/to/signature.png", "x": 400, "y": 700, "width": 150}`
   — width/height auto-detected from the image if omitted.
4. `get_screenshot` to confirm placement; adjust via
   `update_annotations` if needed.
5. For initials on every page, batch one `image` annotation per page
   in a single `add_annotations` call.

**Disclaimer:** This places a visual signature image. It is **not** a
certified or cryptographic digital signature. For legally binding
e-signatures, use a dedicated signing service.

## Supported Sources

- Local files (paths under client MCP roots)
- arXiv (`/abs/` URLs auto-convert to PDF)
- Any direct HTTPS PDF URL (bioRxiv, Zenodo, OSF, etc. — use the
  direct PDF link, not the landing page)

## Out of Scope

- **Summarization / text extraction** — use native Read instead
- **Certified digital signatures** — image stamping only
- **PDF creation** — this works on existing PDFs only
