/*
 * gen_report.js, EPLUS punch report renderer.
 *
 * Reads a build directory (report.config.json, master_report_items.json,
 * sheet_clip_dims_jpg.json, thumbs_uniform/, sheet_clips_jpg/, assets/) and
 * writes one .docx, the file of record. A PDF is a separate, on-request step
 * (scripts/export_pdf.py), never part of the render.
 *
 * What it renders:
 *   - Page 1 of the body is BLANK (own section, no header or footer) in every
 *     cover_mode but "none", so the reviewer can swap in a coversheet and the
 *     page numbers stay right. In "template" mode the cover itself is written
 *     to a SEPARATE file, <output>-Cover.docx: the EPLUS coversheet artwork as
 *     page-anchored floating images with native, config-driven text blocks
 *     measured from the issued coversheet (EP logo and address, eyebrow and
 *     building on the band, client name and address, EP project number and
 *     dates, optional client logo).
 *   - Contents section: a heading, a red delete-before-printing note, and a REAL
 *     Word TOC field (TOC \o "1-1" \h \z \u) whose cached result is one styled
 *     entry per item, each entry a PAGEREF field on the item heading's bookmark
 *     wrapped in an InternalHyperlink. Update Table / F9 regenerates titles,
 *     page numbers and entry count together. features.updateFields makes Word
 *     refresh on open. scripts/fix_bookmark_ids.py runs after this to give the
 *     bookmarks unique numeric ids, which the docx library does not.
 *   - One item per page: Heading 1 with Word's own numbering ("Item N.") and a
 *     bookmark; a meta table (Drawing Sheet, Date Recorded) with the pin clip
 *     spanning both rows at about 3.17in; Item Description; Corrective Action;
 *     an optional red Editor's Note box (internal, deleted before issuing); then
 *     the photo grid.
 *   - Photo grid: fixed two columns, each photo on a 3:4 canvas 1.90in wide
 *     with a numbered, timestamped caption; hairline cell borders so a reviewer
 *     can see where to paste. As many complete rows as fit on the item page,
 *     the rest on headed "(continued)" pages. The "Photos" label carries no
 *     count. An item with no photos gets ONE empty row sized like a real cell
 *     as a paste target, unless its photo_mode is "none".
 *   - Every body page carries the native letterhead (a two-column table: EP
 *     logo + URL images left, "Technology System / Punch List" right, then a
 *     shaded divider paragraph) and a "Page N of M" footer. Never a pasted bitmap.
 *
 * Data keys read from master_report_items.json per item: display_number,
 * plangrid_ref, title, description, corrective_action, sheet_display,
 * date_recorded (the pin's created_at as MM/DD/YYYY; the photo timestamp is
 * only a fallback), deleted_in_plangrid (red banner under the heading plus a
 * TOC marker), photo_paths (basenames under thumbs_uniform/), photo_titles,
 * editor_note, precedent_note, photo_mode. plangrid_ref and
 * field_note_original are carried for traceability and are NEVER rendered.
 *
 * Visit sections (optional, report.config.json): either
 *   "visit_breaks": [{"before": <PlanGrid number>, "title": "Site Visit 2, 08/28/2026"}, ...]
 * or
 *   "visit_sections": "by_date"
 * puts a Heading 1 section title on the page of the first item of each visit
 * (by_date derives the breaks from date_recorded changes and titles them
 * "Site Visit N, MM/DD/YYYY"). Section titles are Heading 1 without item
 * numbering, so the TOC lists them and Word regenerates them with the items.
 * A break whose "before" names no item in the master fails the render.
 *
 * GOTCHAS, all learned the hard way:
 *   - ImageRun.transformation.{width,height} are PIXELS while everything else is twips.
 *   - TableCell rowSpan is declared ONCE on the first row's cell.
 *   - Always render to a NEW filename; the scratch workspace refuses overwrite.
 */
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, ImageRun, AlignmentType,
  Header, Footer, PageNumber, VerticalAlign, LevelFormat, HeadingLevel,
  TabStopType, LeaderType, Tab, Bookmark, InternalHyperlink, PageReference,
  HorizontalPositionRelativeFrom, VerticalPositionRelativeFrom, TextWrappingType,
  TableAnchorType, OverlapType, ImportedXmlComponent,
} = require('docx');

const BUILD = process.argv[2] || path.join(__dirname, '..');
const CFG = JSON.parse(fs.readFileSync(path.join(BUILD, 'report.config.json')));
const OUT = process.argv[3] || path.join(BUILD, CFG.output_filename);

// -------------------------------------------------------------------- docx@9.7.1 bug fixes
// 1. ImportedXmlComponent.fromXmlString() runs the string through xml2js with
//    {compact:false}, which returns a top-level DOCUMENT node (type undefined, name
//    undefined) wrapping the real element in .elements[0]. convertToXmlComponent()'s
//    `case void 0:` treats that wrapper as a real element too, so it emits a literal
//    <undefined>...</undefined> tag around every imported fragment. The XML stays
//    well-formed (every lax parser, including LibreOffice, accepts it), but Word
//    refuses to open a document containing an undeclared element name. The real
//    element survives as the wrapper's first (only) child -- .root[0] -- so unwrap it
//    there before handing it to a Paragraph.
const importXml = (xmlString) => ImportedXmlComponent.fromXmlString(xmlString).root[0];

// 2. DocProperties (the wp:docPr element every ImageRun's Drawing carries) builds a
//    FRESH docPropertiesUniqueNumericIdGen() per instance when no explicit id is
//    passed, so every image in the document gets id="1". Word keys on this id like
//    it keys on bookmark ids, and duplicate docPr ids are a corruption trigger the
//    same way duplicate bookmark ids are (see fix_bookmark_ids.py). Share one counter
//    across the whole document and pass it through altText.id on every ImageRun so
//    each drawing gets a distinct id.
let _docPrIdSeq = 1000;
const nextDocPrId = () => _docPrIdSeq++;
const imageRun = (options) => new ImageRun({
  ...options,
  altText: { title: '', name: '', ...(options.altText || {}), id: nextDocPrId() },
});

const master = JSON.parse(fs.readFileSync(path.join(BUILD, CFG.master_file || 'master_report_items.json')));
const clipDims = JSON.parse(fs.readFileSync(path.join(BUILD, 'sheet_clip_dims_jpg.json')));
const PHOTO_DIR = path.join(BUILD, 'thumbs_uniform');

// ---------------------------------------------------------------- page + brand constants
const PAGE_W = 12240, PAGE_H = 15840;
const MARGIN_LR = 1080;
const MARGIN_TOP = 1800;                              // 1.25", leaves room for the letterhead
const MARGIN_BOTTOM = 1080;
const HEADER_MARGIN = 360;                            // 0.25" from paper edge to letterhead
const USABLE_W = PAGE_W - 2 * MARGIN_LR;              // 10080 dxa = 7.0"
const CONTENT_H = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM - 400;

const BLUE = '44546A';                                // legacy letterhead blue
const DARKGREY = '58595B';
const LIGHTGREY = 'A6A6A5';
const BLUE_TINT = 'E7E9EE';
const ALERT_RED = 'B00000';
const RED_TINT = 'FBE9E9';
const FONT = 'Arial';

// Letterhead is rebuilt natively from its component assets, NOT pasted in as a
// bitmap strip. The strip approach was wrong twice: it is sized to the full page
// (8.0in) but a header paragraph begins at the BODY left margin (0.75in), so it
// overhung the right edge and left dead space on the left. A native table sized to
// USABLE_W lines up with the body margins exactly, at any page size, and stays
// crisp at print resolution. Do not go back to pasting letterhead_strip.png.
const EP_LOGO = fs.readFileSync(path.join(BUILD, 'assets/logos/ep_logo.jpg'));
const EP_URL = fs.readFileSync(path.join(BUILD, 'assets/logos/ep_url.png'));
// native letterhead geometry, all anchored to USABLE_W so it tracks the body margins
const LH_LOGO_W = 2520;                               // ep_logo.jpg  700x141
const LH_LOGO_H = Math.round(LH_LOGO_W * 141 / 700);
const LH_URL_W = 1560;                                // ep_url.png  1416x191
const LH_URL_H = Math.round(LH_URL_W * 191 / 1416);
const LH_LEFT_W = 4600;
const LH_RIGHT_W = USABLE_W - LH_LEFT_W;

// ------------------------------------------------------------------ uniform photo sizing
// Photos live on one 700 x 933 (3:4) canvas so each embedded image is exactly the same size.
// The render width was tuned by rendering one 50-item set at several widths and
// counting the items that stayed on one page:
//   2.50" -> 33/50 items self contained, 81 pages
//   2.25" -> 38/50 items self contained, 78 pages
//   2.10" -> 41/50 items self contained, 76 pages
//   1.90" -> 42/50 items self contained, 76 pages   <-- current value (PHOTO_W_DXA)
// The column count is FIXED at two; nothing here searches column counts. If the field
// set or the text blocks change materially, re-measure the same way rather than
// nudging the constant by eye.
const PHOTO_COLS = 2;
const PHOTO_W_DXA = 2736;                              // 1.90"
const PHOTO_H_DXA = Math.round(PHOTO_W_DXA * 933 / 700); // 3:4 canvas => 2.53"
const PHOTO_ROW_H = PHOTO_H_DXA + 300;                 // caption + cell pad
const PHOTO_COL_W = Math.floor(USABLE_W / PHOTO_COLS);
const CONT_HEADER_H = 620;

// Meta table is deliberately minimal: Drawing Sheet and Date Recorded, nothing else.
// The Location row was removed because PlanGrid's `room` is empty on every pin, so it
// only ever printed a placeholder, which reads as noise rather than information. The
// Photos count row went with it: the photos are visible directly below it. If real
// location data ever becomes available (photo EXIF geotags, say), add the row back
// rather than reviving the placeholder.
//
// The pin clip column is DOUBLE its previous width. With no location data, the clip is
// the only thing on the page that says where this item is, so it earns the space.
const META_LABEL_W = 1650;
const CLIP_COL_W = 4800;
const META_VALUE_W = USABLE_W - META_LABEL_W - CLIP_COL_W;
const CLIP_IMG_W = CLIP_COL_W - 240;

const dxaToPx = (dxa) => Math.floor((dxa / 1440) * 96);

function fmtTimestamp(title) {
  const m = String(title || '').match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
  if (!m) return title || '';
  const [, yyyy, mm, dd, HH, MM] = m;
  return `${mm}/${dd}/${yyyy} ${HH}:${MM}`;
}

function run(text, opts = {}) {
  return new TextRun({ text, font: FONT, ...opts });
}

function noBorders() {
  const none = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
  return { top: none, bottom: none, left: none, right: none };
}

function thinBorders(color = LIGHTGREY) {
  const b = { style: BorderStyle.SINGLE, size: 4, color };
  return { top: b, bottom: b, left: b, right: b };
}

function estimateTextHeightDXA(text, sizeHalfPt, widthDXA) {
  if (!text) return 0;
  const pt = sizeHalfPt / 2;
  const charsPerLine = Math.max(15, Math.floor((widthDXA / 20) / (0.5 * pt)));
  const lines = Math.max(1, Math.ceil(String(text).length / charsPerLine));
  return lines * Math.round(pt * 23);
}

// --------------------------------------------------------------------------- meta table
function sheetClipPathFor(item) {
  const pg = item.plangrid_ref.replace('#', '');
  return path.join(BUILD, 'sheet_clips_jpg', `item_${pg}.jpg`);
}

function metaRowsData(item) {
  // PlanGrid ref is NOT rendered here. It is internal traceability only.
  // Two rows only. See the CLIP_COL_W comment for why Location and Photos are gone.
  //
  // Date Recorded is the PIN's created_at (build_master.py writes it as
  // date_recorded). The earliest photo timestamp is only a fallback for a
  // master built without it: on 2026-09-14 the photo-only rule printed N/A on
  // 27 of 38 items and forced a second delivery.
  const shots = (item.photo_titles || []).map(fmtTimestamp).filter(Boolean).sort();
  const recorded = item.date_recorded || (shots.length ? shots[0].split(' ')[0] : 'N/A');
  return [
    ['Drawing Sheet', item.sheet_display || 'N/A'],
    ['Date Recorded', recorded],
  ];
}

function metaTable(item) {
  const rowsData = metaRowsData(item);
  const clipPath = sheetClipPathFor(item);

  let clipCellChildren;
  if (fs.existsSync(clipPath)) {
    const clipBase = path.basename(clipPath);
    const [cw, ch] = clipDims[clipBase] || [800, 800];
    const clipH = Math.round(CLIP_IMG_W * (ch / cw));
    clipCellChildren = [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [imageRun({
          type: 'jpg',
          data: fs.readFileSync(clipPath),
          transformation: { width: dxaToPx(CLIP_IMG_W), height: dxaToPx(clipH) },
        })],
      }),
    ];
  } else {
    clipCellChildren = [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [run('(no pin clip)', { italics: true, size: 15, color: LIGHTGREY })],
    })];
  }

  const rows = rowsData.map(([label, value], i) => {
    const cells = [
      new TableCell({
        width: { size: META_LABEL_W, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, color: 'auto', fill: BLUE_TINT },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        borders: thinBorders(),
        children: [new Paragraph({ children: [run(label, { bold: true, size: 19, color: BLUE })] })],
      }),
      new TableCell({
        width: { size: META_VALUE_W, type: WidthType.DXA },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        borders: thinBorders(),
        children: [new Paragraph({ children: [run(String(value), { size: 19, color: DARKGREY })] })],
      }),
    ];
    if (i === 0) {
      cells.push(new TableCell({
        width: { size: CLIP_COL_W, type: WidthType.DXA },
        rowSpan: rowsData.length,
        verticalAlign: VerticalAlign.CENTER,
        margins: { top: 60, bottom: 60, left: 60, right: 60 },
        borders: thinBorders(),
        children: clipCellChildren,
      }));
    }
    return new TableRow({ cantSplit: true, children: cells });
  });

  return new Table({
    width: { size: USABLE_W, type: WidthType.DXA },
    columnWidths: [META_LABEL_W, META_VALUE_W, CLIP_COL_W],
    rows,
  });
}

// -------------------------------------------------------------------------- photo grid
// The photo grid is a VISIBLE grid, on purpose. This report gets edited in Word after
// it is generated, and the single most common edit is adding or swapping a photo. With
// borderless cells there is nothing to aim at: the reviewer cannot see where a photo
// would land. Hairline cell borders make the slots legible, and the numbering gives
// every photo a name that can be cited in a comment or a covering email.
//
// Empty slots are drawn but carry NO placeholder text, because this document is
// exported to PDF as-is and any hint text would print in the issued copy.
function photoCaption(item, idx) {
  const stamp = fmtTimestamp(item.photo_titles[idx]);
  return `Photo ${idx + 1}${stamp ? '  |  ' + stamp : ''}`;
}

function photoCell(item, idx) {
  const base = path.basename(item.photo_paths[idx]);
  const file = path.join(PHOTO_DIR, base);
  const children = [];
  try {
    children.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [imageRun({
        type: 'jpg',
        data: fs.readFileSync(file),
        transformation: { width: dxaToPx(PHOTO_W_DXA), height: dxaToPx(PHOTO_H_DXA) },
      })],
    }));
  } catch (e) {
    children.push(new Paragraph({ children: [run('[image unavailable]', { italics: true, size: 16 })] }));
  }
  children.push(new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [run(photoCaption(item, idx), { size: 15, color: LIGHTGREY })],
  }));
  return new TableCell({
    width: { size: PHOTO_COL_W, type: WidthType.DXA },
    margins: { top: 40, bottom: 40, left: 40, right: 40 },
    borders: thinBorders(),
    children,
  });
}

// Sized to match a filled cell so the grid stays square when a row is part full, and
// so a pasted photo lands in a slot of the right height rather than growing the row.
function emptyCell() {
  return new TableCell({
    width: { size: PHOTO_COL_W, type: WidthType.DXA },
    margins: { top: 40, bottom: 40, left: 40, right: 40 },
    borders: thinBorders(),
    verticalAlign: VerticalAlign.CENTER,
    // An empty cell holding an empty paragraph collapses to a single text line,
    // so the slot is invisible as a paste target. Give it the height of a
    // filled cell.
    children: [new Paragraph({
      spacing: { before: Math.round(PHOTO_H_DXA / 2), after: Math.round(PHOTO_H_DXA / 2) },
      children: [run('')],
    })],
  });
}

function emptyPhotoRow() {
  return new Table({
    width: { size: USABLE_W, type: WidthType.DXA },
    columnWidths: Array(PHOTO_COLS).fill(PHOTO_COL_W),
    rows: [new TableRow({
      cantSplit: true,
      children: Array.from({ length: PHOTO_COLS }, emptyCell),
    })],
  });
}

function photoTable(item, start, end) {
  const rows = [];
  for (let i = start; i < end; i += PHOTO_COLS) {
    const cells = [];
    for (let c = 0; c < PHOTO_COLS; c++) {
      cells.push(i + c < end ? photoCell(item, i + c) : emptyCell());
    }
    rows.push(new TableRow({ cantSplit: true, children: cells }));
  }
  return new Table({
    width: { size: USABLE_W, type: WidthType.DXA },
    columnWidths: Array(PHOTO_COLS).fill(PHOTO_COL_W),
    rows,
  });
}

// ------------------------------------------------------------------------ item overhead
const NOTE_SIZE = 17;

function estimateOverheadDXA(item, opts = {}) {
  let h = 400;
  if (opts.visitHeading) h += 700;                       // section title above the item heading
  h += estimateTextHeightDXA(item.title, 26, USABLE_W - 1200);
  if (item.deleted_in_plangrid) h += 360;               // the DELETED IN PLANGRID banner

  const textRows = metaRowsData(item)
    .reduce((s, [, v]) => s + estimateTextHeightDXA(String(v), 19, META_VALUE_W) + 100, 0);
  const clipBase = path.basename(sheetClipPathFor(item));
  const [cw, ch] = clipDims[clipBase] || [800, 800];
  const clipH = Math.round(CLIP_IMG_W * (ch / cw)) + 280;
  h += Math.max(textRows, clipH) + 100;

  h += 300 + estimateTextHeightDXA(item.description, 20, USABLE_W) + 80;
  h += 300 + estimateTextHeightDXA(item.corrective_action, 20, USABLE_W) + 80;
  // An item with no photos now renders one empty grid row, so reserve it --
  // unless photo_mode "none" says no photos apply to this item at all.
  if (!item.photo_paths.length && item.photo_mode !== 'none') h += PHOTO_ROW_H;
  // no allowance for field_note_original: that block is no longer rendered (see itemSection)
  if (item.editor_note || item.precedent_note) {
    if (item.editor_note) h += estimateTextHeightDXA(item.editor_note, NOTE_SIZE, USABLE_W - 400) + 60;
    if (item.precedent_note) h += estimateTextHeightDXA(item.precedent_note, NOTE_SIZE, USABLE_W - 400) + 60;
    h += 280;
  }
  h += 300;
  return h;
}

function labelPara(text) {
  return new Paragraph({
    keepNext: true,
    spacing: { after: 50 },
    children: [run(text, { bold: true, size: 21, color: BLUE })],
  });
}

function bodyPara(text) {
  return new Paragraph({
    keepNext: true, keepLines: true,
    spacing: { after: 100 },
    children: [run(text, { size: 20, color: DARKGREY })],
  });
}

/**
 * Editor's Note (formerly Reviewer Flag): boxed red callout, internal only.
 * Carries: the note text, then optional supporting EPLUS precedent basis.
 */
function editorNoteBlock(lines) {
  return new Table({
    width: { size: USABLE_W, type: WidthType.DXA },
    columnWidths: [USABLE_W],
    rows: [new TableRow({
      cantSplit: true,
      children: [new TableCell({
        width: { size: USABLE_W, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, color: 'auto', fill: RED_TINT },
        margins: { top: 90, bottom: 90, left: 140, right: 140 },
        borders: {
          top: { style: BorderStyle.SINGLE, size: 4, color: ALERT_RED },
          bottom: { style: BorderStyle.SINGLE, size: 4, color: ALERT_RED },
          left: { style: BorderStyle.SINGLE, size: 18, color: ALERT_RED },
          right: { style: BorderStyle.SINGLE, size: 4, color: ALERT_RED },
        },
        children: [
          new Paragraph({
            spacing: { after: 30 },
            children: [run("EDITOR'S NOTE, internal only, delete before issuing", { bold: true, size: 18, color: ALERT_RED })],
          }),
          ...lines.map(([label, text]) => new Paragraph({
            spacing: { after: 30 },
            children: [
              run(`${label}: `, { bold: true, size: 18, color: ALERT_RED }),
              run(text, { size: 18, color: ALERT_RED }),
            ],
          })),
        ],
      })],
    })],
  });
}

// ------------------------------------------------------------------------ deleted banner
// A pin PlanGrid has deleted or archived, kept in the report by the intake
// decision "keep, marked" (consolidate.py --keep-deleted) so the item numbering
// still matches the pull. The banner is red and unmistakable, like every other
// editor-facing mark, because the reviewer decides whether it ships.
const DELETED_BANNER = 'DELETED IN PLANGRID';
function deletedBanner() {
  return new Paragraph({
    keepNext: true,
    spacing: { before: 0, after: 100 },
    shading: { type: ShadingType.CLEAR, color: 'auto', fill: RED_TINT },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: ALERT_RED, space: 4 } },
    children: [
      run(`${DELETED_BANNER}. `, { bold: true, size: 18, color: ALERT_RED }),
      run('This pin is deleted or archived in PlanGrid and is retained here so the item numbering matches the pull. Reviewer decides whether it issues.', { size: 18, color: ALERT_RED }),
    ],
  });
}

// ------------------------------------------------------------------------- item section
// opts.visitHeading: this item opens a visit section, so the section title
// paragraph (emitted by the caller) carries the page break and the item
// heading must not add a second one.
function itemSection(item, opts = {}) {
  const children = [];
  const n = item.photo_paths.length;

  // Item heading. Uses Heading 1 style so the Word TOC picks it up automatically, AND uses
  // Word's native numbering so deleting an item renumbers the rest.
  children.push(new Paragraph({
    heading: HeadingLevel.HEADING_1,
    numbering: { reference: 'punch-items', level: 0 },
    pageBreakBefore: !opts.visitHeading,
    keepNext: true,
    spacing: { before: 0, after: 120 },
    children: [new Bookmark({
      id: bookmarkFor(item),
      children: [run(item.title, { bold: true, size: 26, color: BLUE })],
    })],
  }));

  if (item.deleted_in_plangrid) children.push(deletedBanner());

  children.push(metaTable(item));
  children.push(new Paragraph({ text: '', spacing: { after: 80 }, keepNext: true }));

  children.push(labelPara('Item Description'));
  children.push(bodyPara(item.description || '(no description available)'));

  children.push(labelPara('Corrective Action'));
  children.push(bodyPara(item.corrective_action));

  // The verbatim pin note is NOT rendered. This report is written BY the field
  // engineer, so quoting their own note back at them reads as third person. The
  // text is still carried on the record (field_note in data/drafted_items.json and
  // field_note_original here) for traceability and for the review spreadsheet.

  const internal = [];
  if (item.editor_note) internal.push(['Note', item.editor_note]);
  if (item.precedent_note) internal.push(['EPLUS precedent basis', item.precedent_note]);
  if (internal.length) {
    children.push(editorNoteBlock(internal));
    children.push(new Paragraph({ text: '', spacing: { after: 60 }, keepNext: true }));
  }

  // Photo pagination.
  // Rule for small sets (n <= 4): always try to place them all on the item page. Word's
  // pagination will either fit them or push the whole photo block to the following page,
  // which reads as a natural page break. Do NOT use keepNext on the "Photos (n)" label,
  // so it does not drag the photo table forward and force a "Photos (n), see following
  // page" ghost. A page break, if forced, is clean: whole block moves together.
  // Rule for large sets (n > 4): fill whatever room is left on the item page (down to
  // one row of photos if that is all that will fit), then spill onto headed continuation
  // pages. This mirrors the v0.6 behavior for the 13, 14, and 21 photo items.
  const remaining = CONTENT_H - estimateOverheadDXA(item, opts);
  const rowsOnFirst = Math.max(0, Math.floor(remaining / PHOTO_ROW_H));
  const rowsPerCont = Math.max(1, Math.floor((CONTENT_H - CONT_HEADER_H) / PHOTO_ROW_H));
  const GRID = PHOTO_COLS * 2;
  const capacityFirst = rowsOnFirst * PHOTO_COLS;
  // Priority is "no blank space". For every item, fill the room on the item page with as
  // many complete 2-column rows as will fit, then spill the rest onto headed continuation
  // pages. Every page still reads as a clean 2-column grid; a 4-photo item that will not
  // fit as a full 2x2 alongside the write-up shows 2 photos on the item page and 2 on the
  // continuation page rather than blanking out the item page. n <= 2 special-cases to
  // "always try" since Word can push the whole label + row block when it is really tight.
  const firstCount = n === 0 ? 0
    : n <= PHOTO_COLS ? n
    : Math.max(0, Math.min(n, capacityFirst));

  // photo_mode "none" (set during the wording review) means no photos apply to
  // this item: no label, no grid, nothing to paste into. Any other value on a
  // photo-less item renders the blank paste-target grid below.
  const suppressPhotos = n === 0 && item.photo_mode === 'none';

  if (!suppressPhotos) {
    children.push(new Paragraph({
      spacing: { after: 60 },
      // No count in the label. The count goes stale the moment anyone adds or
      // removes a photo in Word, nothing downstream reads it, and the photos are
      // visible immediately below. Standing rule, not a per-report tweak.
      children: [run(
        firstCount >= n ? 'Photos'
          : firstCount === 0 ? 'Photos, see following page'
          : 'Photos',
        { bold: true, size: 20, color: BLUE })],
    }));

    // An item with no photos still gets one empty row. Pins logged without a
    // photo are the ones most likely to have one added by hand later, so the slot
    // has to be there to paste into.
    children.push(n === 0 ? emptyPhotoRow() : photoTable(item, 0, firstCount));
  }

  let idx = firstCount;
  while (idx < n) {
    const end = Math.min(n, idx + rowsPerCont * PHOTO_COLS);
    children.push(new Paragraph({
      pageBreakBefore: true,
      keepNext: true,
      spacing: { after: 40 },
      children: [
        run(`Item ${item.display_number} (continued): `, { bold: true, size: 22, color: BLUE }),
        run(item.title, { bold: true, size: 22, color: BLUE }),
      ],
    }));
    children.push(new Paragraph({
      keepNext: true,
      spacing: { after: 80 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LIGHTGREY, space: 2 } },
      children: [run('Photos (continued)', { size: 17, color: DARKGREY })],
    }));
    children.push(photoTable(item, idx, end));
    idx = end;
  }

  children.push(new Paragraph({
    spacing: { before: 160, after: 0 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LIGHTGREY, space: 1 } },
    children: [run('')],
  }));
  return children;
}

// --------------------------------------------------------------- cover + TOC (no summary)
const withPrecedent = master.filter(m => m.precedent_note).length;
const editorNoted = master.filter(m => m.editor_note).length;
const totalPhotos = master.reduce((s, m) => s + m.photo_paths.length, 0);

// ------------------------------------------------------------------------------- cover
// Rebuilt from a previously issued EPLUS coversheet, which is the design EPLUS has been
// putting on these reports. The two raster pieces ARE the artwork and are reused as
// shipped: cover_hero.jpg is stock brand imagery and cover_bands.png is the EP diagonal
// band graphic, a full-page transparent overlay. Everything else, all the text and all
// the geometry, is native, so it tracks page size and is editable in Word.
//
// Geometry is taken from the reference document's own anchors, converted to page
// relative offsets:
//     bands   8.49 x 10.98in at (0.00, 0.01)   full bleed, drawn OVER the hero
//     hero    8.53 x  6.37in at (0.00, 1.01)   leaves a white band at top for the logos
// The reference gives bands a higher relativeHeight than the hero, so the bands sit on
// top. docx derives z order from document order, so the hero must be emitted FIRST.
//
// The client logo is deliberately NOT bundled with this skill: it is the end client's
// trademark and it changes per project. Supply it per project as
// build/assets/cover/client_logo.png and it renders bottom right; omit it and the cover
// simply renders without it.
const EMU_PER_IN = 914400;
const inEMU = (n) => Math.round(n * EMU_PER_IN);
// cover_mode in report.config.json:
//   template  write <output>-Cover.docx (this file's layout) and leave page 1 of the body blank
//   supplied  the reviewer has a coversheet; body page 1 blank, no cover written
//   blank     body page 1 blank only, no cover written
//   none      no cover page at all; the Table of Contents is page 1
// include_cover: false (legacy) means none.
const COVER_MODE = CFG.cover_mode || (CFG.include_cover === false ? 'none' : 'template');
const BLANK_FIRST_PAGE = COVER_MODE !== 'none';
const WRITE_COVER = COVER_MODE === 'template';
const COVER_OUT = OUT.replace(/\.docx$/i, '') + '-Cover.docx';
const COVER_DIR = path.join(BUILD, 'assets/cover');
// 0.25in from the paper edge, the same inset as the body pages' letterhead
// (HEADER_MARGIN), so the cover logos and the interior letterhead line up.
const COVER_LOGO_Y = HEADER_MARGIN;

function coverBackgroundRuns() {
  const runs = [];
  const layers = [
    { file: 'cover_hero.jpg', type: 'jpg', w: 8.53, h: 6.37, x: 0.0, y: 1.01 },
    { file: 'cover_bands.png', type: 'png', w: 8.49, h: 10.98, x: 0.0, y: 0.01 },
  ];
  for (const l of layers) {
    const p = path.join(COVER_DIR, l.file);
    if (!fs.existsSync(p)) continue;
    runs.push(imageRun({
      type: l.type,
      data: fs.readFileSync(p),
      transformation: { width: Math.round(l.w * 96), height: Math.round(l.h * 96) },
      floating: {
        horizontalPosition: { relative: HorizontalPositionRelativeFrom.PAGE, offset: inEMU(l.x) },
        verticalPosition: { relative: VerticalPositionRelativeFrom.PAGE, offset: inEMU(l.y) },
        behindDocument: true,
        allowOverlap: true,
        wrap: { type: TextWrappingType.NONE },
      },
    }));
  }
  return runs;
}

// ------------------------------------------------------------------ cover layout
// Measured from the coversheet EPLUS issues (2026-09-10 field reference, US Letter):
//
//   EP logo                     top left, in the white band above the artwork
//   address line                x 0.75in  y 1.09in  10.5pt   (constant, below)
//   eplusadvisors.com           x 0.75in  y 1.28in  14pt
//   eyebrow                     x 0.75in  y 3.56in  16pt     white, on the dark band
//   building (title)            x 0.75in  y 4.04in  22pt     white, bold
//   client name                 right-aligned to x 7.75in, y 8.38in, 20pt bold
//   client address lines        right-aligned to x 7.75in, from y 8.71in, 14pt
//   EP Project No / Inspection Date / Issuance Date / Inspector
//                               x 1.43in  y 9.25in  12pt, one line each, label bold
//   client logo (optional)      x 4.96in  y 9.36in  3.19 x 0.73in box, bottom right
//
// The reference is set in Montserrat; the seats do not carry that font, so this
// uses the document font (Arial) at the same sizes. When the fleet standardises
// a brand font, FONT is the one constant to change.
//
// Every block is a page-anchored floating table (see floatingBlock), never a
// pasted bitmap: the text tracks the page and stays editable in Word.
const EPLUS_ADDRESS = '9018 Heritage Parkway  •  Suite 1000  •  Woodridge, IL 60517  •  P: 630.786.4200  •  F: 630-786-4201';
const EPLUS_URL = 'eplusadvisors.com';
const inDxa = (n) => Math.round(n * 1440);

function fmtDate(v) {
  // MM/DD/YYYY on the cover. Accepts ISO (YYYY-MM-DD), the legacy "Site walk:
  // Month D, YYYY" strings, or anything Date can parse; passes through otherwise.
  if (!v) return '';
  const s = String(v).replace(/^Site walk:\s*/i, '').trim();
  let m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) return `${m[2]}/${m[3]}/${m[1]}`;
  if (/^\d{2}\/\d{2}\/\d{4}$/.test(s)) return s;
  const d = new Date(s);
  if (!isNaN(d)) {
    const p = (n) => String(n).padStart(2, '0');
    return `${p(d.getMonth() + 1)}/${p(d.getDate())}/${d.getFullYear()}`;
  }
  return s;
}

function floatingBlock(x, y, w, children, fill) {
  return new Table({
    float: {
      horizontalAnchor: TableAnchorType.PAGE,
      verticalAnchor: TableAnchorType.PAGE,
      absoluteHorizontalPosition: x,
      absoluteVerticalPosition: y,
      overlap: OverlapType.OVERLAP,
    },
    width: { size: w, type: WidthType.DXA },
    columnWidths: [w],
    borders: noBorders(),
    rows: [new TableRow({
      cantSplit: true,
      children: [new TableCell({
        width: { size: w, type: WidthType.DXA },
        borders: noBorders(),
        margins: { top: 0, bottom: 0, left: 0, right: 0 },
        ...(fill ? { shading: { type: ShadingType.CLEAR, color: 'auto', fill } } : {}),
        children,
      })],
    })],
  });
}

const metaLine = (label, value) => new Paragraph({
  spacing: { before: 0, after: 40, line: 276, lineRule: 'auto' },
  children: [
    run(`${label}: `, { bold: true, size: 24, color: DARKGREY }),
    run(value, { size: 24, color: DARKGREY }),
  ],
});

// Top left: EP logo, the address line, the URL. Native text under the brand mark.
const coverBrandBlock = floatingBlock(inDxa(0.75), inDxa(0.35), inDxa(7.0), [
  new Paragraph({
    spacing: { before: 0, after: 80 },
    children: [imageRun({
      type: 'jpg', data: EP_LOGO,
      transformation: { width: dxaToPx(LH_LOGO_W), height: dxaToPx(LH_LOGO_H) },
    })],
  }),
  new Paragraph({ spacing: { before: 0, after: 20 }, children: [run(EPLUS_ADDRESS, { size: 17, color: DARKGREY })] }),
  new Paragraph({ spacing: { before: 0, after: 0 }, children: [run(EPLUS_URL, { size: 24, color: DARKGREY })] }),
]);

// Left, on the dark band: eyebrow, short white rule, building name.
const coverTitleBlock = floatingBlock(inDxa(0.75), inDxa(3.50), inDxa(3.4), [
  new Paragraph({
    spacing: { before: 0, after: 60 },
    children: [run(CFG.cover_eyebrow || 'Technology Site Inspection', { size: 32, color: 'FFFFFF' })],
  }),
  new Paragraph({
    spacing: { before: 0, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: 'FFFFFF', space: 1 } },
    indent: { right: inDxa(1.0) },
    children: [run('', { size: 2 })],
  }),
  new Paragraph({
    spacing: { before: 0, after: 0 },
    children: [run(CFG.cover_subtitle || '', { bold: true, size: 44, color: 'FFFFFF' })],
  }),
]);

// Bottom right: client display name and address, right-aligned to the text edge.
const clientName = CFG.client_display_name || CFG.cover_title || '';
const coverClientBlock = floatingBlock(inDxa(4.25), inDxa(8.32), inDxa(3.5), [
  new Paragraph({
    alignment: AlignmentType.RIGHT,
    spacing: { before: 0, after: 60 },
    children: [run(clientName, { bold: true, size: 40, color: BLUE })],
  }),
  ...(CFG.site_address || []).map((line) => new Paragraph({
    alignment: AlignmentType.RIGHT,
    spacing: { before: 0, after: 20 },
    children: [run(line, { size: 28, color: DARKGREY })],
  })),
]);

// Bottom left: the four meta lines. EP project number first, as on the issued sheet.
const coverMetaBlock = floatingBlock(inDxa(1.43), inDxa(9.20), inDxa(3.3), [
  ...(CFG.ep_project_no && !String(CFG.ep_project_no).startsWith('<')
    ? [metaLine('EP Project No', String(CFG.ep_project_no))] : []),
  metaLine('Inspection Date', fmtDate(CFG.inspection_date || CFG.walk_date)),
  metaLine('Issuance Date', fmtDate(CFG.issuance_date)),
  ...(CFG.inspector ? [metaLine('Inspector', CFG.inspector)] : []),
]);

// Bottom right: the client's logo, only when a file is present. It is the end
// client's trademark and changes per project, so it is never bundled. Fitted
// inside a 3.19 x 0.73in box, aspect preserved.
function coverClientLogo() {
  const p = path.join(COVER_DIR, 'client_logo.png');
  if (!fs.existsSync(p)) return [];
  let w = 3.19, h = 0.73;
  try {
    const buf = fs.readFileSync(p);
    // PNG IHDR: width at byte 16, height at byte 20 (big-endian)
    const pw = buf.readUInt32BE(16), ph = buf.readUInt32BE(20);
    if (pw > 0 && ph > 0) {
      const scale = Math.min(3.19 / pw, 0.73 / ph);
      w = pw * scale; h = ph * scale;
    }
  } catch (e) { /* keep the box size */ }
  return [new Paragraph({
    spacing: { before: 0, after: 0 },
    children: [imageRun({
      type: 'png', data: fs.readFileSync(p),
      transformation: { width: Math.round(w * 96), height: Math.round(h * 96) },
      floating: {
        horizontalPosition: { relative: HorizontalPositionRelativeFrom.PAGE, offset: inEMU(8.15 - w) },
        verticalPosition: { relative: VerticalPositionRelativeFrom.PAGE, offset: inEMU(9.36) },
        allowOverlap: true,
        wrap: { type: TextWrappingType.NONE },
      },
    })],
  })];
}

const coverPage = [
  new Paragraph({ children: coverBackgroundRuns(), spacing: { before: 0, after: 0 } }),
  coverBrandBlock,
  coverTitleBlock,
  coverClientBlock,
  coverMetaBlock,
  ...coverClientLogo(),
  // A floating table must be followed by an anchor paragraph in the flow, or Word has
  // nothing to hang the section's final properties on.
  new Paragraph({ spacing: { before: 0, after: 0 }, children: [run('', { size: 2 })] }),
];

const cover = [
  // ----- Table of Contents -----
  // No pageBreakBefore: the cover is its own section, so the section break already
  // starts this page. Adding a break here would emit a blank page between them.
  new Paragraph({
    children: [run('Table of Contents', { bold: true, size: 28, color: BLUE })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: BLUE, space: 2 } },
    spacing: { after: 160 },
  }),
  // This is an INSTRUCTION TO THE EDITOR, not report content, and it would otherwise
  // print in the issued PDF looking like part of the document. Styled as a red
  // delete-before-printing callout so it is unmistakably not for the reader, matching
  // the Editor's Note treatment used on each item.
  new Paragraph({
    spacing: { after: 200 },
    children: [
      run('DELETE PRIOR TO PRINTING, ', { bold: true, size: 17, color: ALERT_RED }),
      run('click any entry to jump to that item. Page numbers update automatically in Word; press Ctrl+A then F9 to refresh them manually.', { italics: true, size: 17, color: ALERT_RED })],
  }),
];

// The contents block is a REAL Word TOC field whose CACHED RESULT is the styled
// entry list below (the exact structure Word itself saves). On open the cached
// entries show immediately -- nothing looks broken -- and Update Table / Ctrl+A F9
// regenerates titles, page numbers AND entry count together, which is what the
// hand-built hybrid could never do: deleting an item used to renumber the body
// while the TOC silently rotted (field evidence 2026-08-28, two reports same day).
// Regenerated entries take the TOC1 paragraph style defined on the Document, so
// the look survives regeneration.
function bookmarkFor(item) {
  return `punchitem${item.display_number}`;
}

// ------------------------------------------------------------------ visit sections
// Explicit breaks from the config win; "by_date" derives them from the pin
// dates build_master.py wrote. Either way the result is validated against the
// master so a typo in the config fails the render instead of silently
// rendering a flat report.
function visitBreaks() {
  const refOf = (m) => String(m.plangrid_ref).replace('#', '');
  const refs = new Set(master.map(refOf));
  let breaks = [];
  if (Array.isArray(CFG.visit_breaks) && CFG.visit_breaks.length) {
    breaks = CFG.visit_breaks.map((b, i) => ({
      before: String(b.before).replace('#', ''),
      title: b.title || `Site Visit ${i + 1}`,
    }));
  } else if (CFG.visit_sections === 'by_date') {
    let last = null, n = 0;
    for (const m of master) {
      const d = m.date_recorded || null;
      if (d !== last) {
        n += 1;
        breaks.push({ before: refOf(m), title: `Site Visit ${n}, ${d || 'date not recorded'}` });
        last = d;
      }
    }
    if (breaks.length < 2) breaks = [];      // one date is not a multi-visit report
  }
  const bad = breaks.filter(b => !refs.has(b.before)).map(b => b.before);
  if (bad.length) {
    throw new Error(`visit_breaks: "before" names PlanGrid item(s) not in the master: ${bad.join(', ')}`);
  }
  return breaks;
}
const VISIT_BREAKS = visitBreaks();
const visitBookmark = (i) => `visit${i + 1}`;

function visitHeading(brk, i) {
  // Heading 1, NO item numbering, so Word's TOC lists it with the items and
  // "Update Table" keeps it. Carries the page break for the item that follows.
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore: true,
    keepNext: true,
    spacing: { before: 0, after: 200 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: BLUE, space: 2 } },
    children: [new Bookmark({
      id: visitBookmark(i),
      children: [run(brk.title, { bold: true, size: 30, color: BLUE })],
    })],
  });
}

function tocEntry(item) {
  const label = `Item ${item.display_number}.  ${item.title}`
    + (item.deleted_in_plangrid ? '  (deleted in PlanGrid)' : '');
  return tocLine(bookmarkFor(item), label, {});
}

function tocLine(anchor, label, style) {
  // The page number is a REAL Word PAGEREF FIELD, not static text.
  //
  // It used to be static text harvested from a LibreOffice dry render. Word
  // paginates differently from LibreOffice (font metrics, image scaling), so those
  // numbers were wrong as soon as the file was opened in Word, and being plain text
  // they never recalculated. The old two-pass render existed only because a field
  // renders blank when LibreOffice converts to PDF without updating fields. We no
  // longer produce the PDF here, Word does, and Word updates fields on export, so
  // the field approach is now strictly correct.
  //
  // Paired with `features: { updateFields: true }` on the Document, which makes Word
  // refresh these on open. Ctrl+A then F9 forces it manually.
  //
  // Both halves are wrapped in an InternalHyperlink so the entry is clickable.
  return new Paragraph({
    spacing: { after: 40, ...(style.before ? { before: style.before } : {}) },
    tabStops: [{ type: TabStopType.RIGHT, position: USABLE_W, leader: LeaderType.DOT }],
    children: [
      new InternalHyperlink({ anchor, children: [run(label, { size: 19, color: style.color || DARKGREY, bold: !!style.bold })] }),
      new TextRun({ children: [new Tab()], font: FONT, size: 19, color: LIGHTGREY }),
      new InternalHyperlink({
        anchor,
        children: [
          run('p. ', { size: 19, color: DARKGREY, bold: true }),
          new PageReference(anchor, { font: FONT, size: 19, color: DARKGREY, bold: true }),
        ],
      }),
    ],
  });
}

const W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"';
const fldChar = (type) => importXml(`<w:r ${W_NS}><w:fldChar w:fldCharType="${type}"/></w:r>`);
// Canonical instruction form: leading/trailing space, \h for hyperlinked entries,
// \z (no leader in web view), \u (outline levels). \o "1-1" collects Heading 1,
// which is what every item heading uses.
const tocInstr = () => importXml(`<w:r ${W_NS}><w:instrText xml:space="preserve"> TOC \\o "1-1" \\h \\z \\u </w:instrText></w:r>`);

// One pass builds both the TOC's cached entries and the body, so a visit
// heading always appears in both places or neither.
const breakBefore = (item) => VISIT_BREAKS.findIndex(b => b.before === String(item.plangrid_ref).replace('#', ''));

cover.push(new Paragraph({ spacing: { after: 0 }, children: [fldChar('begin'), tocInstr(), fldChar('separate')] }));
const body = [];
for (const item of master) {
  const bi = breakBefore(item);
  if (bi >= 0) {
    cover.push(tocLine(visitBookmark(bi), VISIT_BREAKS[bi].title, { bold: true, color: BLUE, before: bi ? 120 : 0 }));
    body.push(visitHeading(VISIT_BREAKS[bi], bi));
  }
  cover.push(tocEntry(item));
  body.push(...itemSection(item, { visitHeading: bi >= 0 }));
}
cover.push(new Paragraph({ spacing: { after: 0 }, children: [fldChar('end')] }));

// ------------------------------------------------------------------------------ assemble
const children = [...cover, ...body];

// The letterhead is one page wide image. It sits inside the header space and renders on
// every page. No first page override, no distinction between the cover/TOC and item pages.
const letterheadHeader = new Header({
  children: [
    new Table({
      width: { size: USABLE_W, type: WidthType.DXA },
      columnWidths: [LH_LEFT_W, LH_RIGHT_W],
      borders: noBorders(),
      rows: [
        new TableRow({
          cantSplit: true,
          children: [
            new TableCell({
              width: { size: LH_LEFT_W, type: WidthType.DXA },
              borders: noBorders(),
              margins: { top: 0, bottom: 0, left: 0, right: 0 },
              verticalAlign: VerticalAlign.TOP,
              children: [
                new Paragraph({
                  spacing: { before: 0, after: 60 },
                  children: [imageRun({
                    type: 'jpg', data: EP_LOGO,
                    transformation: { width: dxaToPx(LH_LOGO_W), height: dxaToPx(LH_LOGO_H) },
                  })],
                }),
                new Paragraph({
                  spacing: { before: 0, after: 0 },
                  children: [imageRun({
                    type: 'png', data: EP_URL,
                    transformation: { width: dxaToPx(LH_URL_W), height: dxaToPx(LH_URL_H) },
                  })],
                }),
              ],
            }),
            new TableCell({
              width: { size: LH_RIGHT_W, type: WidthType.DXA },
              borders: noBorders(),
              margins: { top: 0, bottom: 0, left: 0, right: 0 },
              verticalAlign: VerticalAlign.TOP,
              children: [
                new Paragraph({
                  alignment: AlignmentType.RIGHT,
                  spacing: { before: 40, after: 0 },
                  children: [run('Technology System', { size: 40, color: BLUE })],
                }),
                new Paragraph({
                  alignment: AlignmentType.RIGHT,
                  spacing: { before: 0, after: 0 },
                  children: [run('Punch List', { size: 40, color: BLUE })],
                }),
              ],
            }),
          ],
        }),
      ],
    }),
    // Divider is a SHADED PARAGRAPH, not a border: LibreOffice clamps thick
    // borders to hairlines when converting to PDF, so a border would vanish.
    new Paragraph({
      spacing: { before: 100, after: 0, line: 120, lineRule: 'exact' },
      shading: { type: ShadingType.CLEAR, fill: BLUE, color: 'auto' },
      children: [run('', { size: 2 })],
    }),
  ],
});

// Footer wording is derived, not free text: the letterhead says Technology
// System / Punch List and the footer says the same, whatever the file is called.
const footerText = CFG.footer_text
  || `Engineering PLUS  •  ${[CFG.client_display_name || CFG.cover_title, CFG.cover_subtitle].filter(Boolean).join(' ')} Technology System Punch List`;
const footer = new Footer({
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    border: { top: { style: BorderStyle.SINGLE, size: 4, color: LIGHTGREY, space: 4 } },
    children: [
      run(`${footerText}  •  Page `, { size: 14, color: LIGHTGREY }),
      new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 14, color: LIGHTGREY }),
      run(' of ', { size: 14, color: LIGHTGREY }),
      new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 14, color: LIGHTGREY }),
    ],
  })],
});

const doc = new Document({
  features: { updateFields: true },     // prompts Word to update the TOC page numbers on open
  styles: {
    default: { document: { run: { font: FONT, color: DARKGREY, size: 21 } } },
    paragraphStyles: [{
      id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
      run: { bold: true, size: 26, color: BLUE, font: FONT },
      paragraph: { spacing: { before: 0, after: 120 } },
    }, {
      // Style Word applies to entries it regenerates inside the TOC field. Matches
      // tocEntry(): dot-leader right tab at the text edge, same size and colour.
      id: 'TOC1', name: 'TOC 1', basedOn: 'Normal', next: 'Normal',
      run: { size: 19, color: DARKGREY, font: FONT },
      paragraph: {
        spacing: { after: 40 },
        tabStops: [{ type: TabStopType.RIGHT, position: USABLE_W, leader: LeaderType.DOT }],
      },
    }],
  },
  numbering: {
    config: [{
      reference: 'punch-items',
      levels: [{
        level: 0,
        format: LevelFormat.DECIMAL,
        text: 'Item %1.',
        alignment: AlignmentType.LEFT,
        style: {
          run: { bold: true, size: 26, color: BLUE, font: FONT },
          paragraph: { indent: { left: 1260, hanging: 1260 } },
        },
      }],
    }],
  },
  sections: [
    // Page 1 of the body is BLANK in every mode but "none": its own section, no
    // header, no footer, nothing on it. The reviewer's workflow is to replace
    // page 1 of the exported PDF with the coversheet (theirs, or the one this
    // script writes to a separate file), so the body's page numbers and its
    // "of N" count are right without any field tricks. In "none" mode the
    // Table of Contents is page 1.
    ...(BLANK_FIRST_PAGE ? [{
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: { top: 720, bottom: 720, left: MARGIN_LR, right: MARGIN_LR, header: 0, footer: 0 },
        },
      },
      children: [new Paragraph({ spacing: { before: 0, after: 0 }, children: [run('', { size: 2 })] })],
    }] : []),
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: {
            top: MARGIN_TOP, bottom: MARGIN_BOTTOM,
            left: MARGIN_LR, right: MARGIN_LR,
            header: HEADER_MARGIN, footer: 500,
          },
        },
      },
      headers: { default: letterheadHeader },
      footers: { default: footer },
      children,
    },
  ],
});

// The cover is a SEPARATE document: one page, its own branding, no letterhead
// header and no page footer. Written only in "template" mode; in "supplied"
// mode the reviewer already has a cover, and in "blank" mode they will add one.
const coverDoc = WRITE_COVER ? new Document({
  styles: { default: { document: { run: { font: FONT, color: DARKGREY, size: 21 } } } },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: 720, bottom: 720, left: MARGIN_LR, right: MARGIN_LR, header: 0, footer: 0 },
      },
    },
    children: coverPage,
  }],
}) : null;

Packer.toBuffer(doc).then(async (buf) => {
  fs.writeFileSync(OUT, buf);
  console.log('wrote', OUT, (buf.length / 1048576).toFixed(1), 'MB', `(cover_mode=${COVER_MODE}${BLANK_FIRST_PAGE ? ', page 1 blank' : ''})`);
  if (coverDoc) {
    const cbuf = await Packer.toBuffer(coverDoc);
    fs.writeFileSync(COVER_OUT, cbuf);
    console.log('wrote', COVER_OUT, (cbuf.length / 1048576).toFixed(1), 'MB', '(cover, separate file)');
  }
  const undetermined = master.filter(m => m.corrective_action.startsWith('N/A')).length;
  const deleted = master.filter(m => m.deleted_in_plangrid).length;
  const undated = master.filter(m => !m.date_recorded).length;
  console.log(`items=${master.length} precedent=${withPrecedent} editor_notes=${editorNoted} undetermined=${undetermined} photos=${totalPhotos}`
    + ` visit_sections=${VISIT_BREAKS.length} deleted_marked=${deleted}`
    + (undated ? ` DATE_RECORDED_MISSING=${undated}` : ''));
});
