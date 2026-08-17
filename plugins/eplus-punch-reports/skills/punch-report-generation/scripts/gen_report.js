const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType, ImageRun, AlignmentType,
  Header, Footer, PageNumber, VerticalAlign,
} = require('docx');

// Build directory holds master_report_items.json, thumb_dims.json,
// sheet_clip_dims_jpg.json, assets/logos/, and the thumb/clip images.
//   node gen_report.js [buildDir] [outFile]
// Items to leave out entirely (camera misfires, pins confirmed not to belong)
// come from OMIT_NUMBERS, e.g.  OMIT_NUMBERS=1,2 node gen_report.js
const BUILD = process.argv[2] || __dirname;
const OUT_FILE = process.argv[3] || path.join(BUILD, 'Punch-Report-DRAFT.docx');

const masterFull = JSON.parse(fs.readFileSync(path.join(BUILD, 'master_report_items.json')));
const dims = JSON.parse(fs.readFileSync(path.join(BUILD, 'thumb_dims.json')));
const clipDims = JSON.parse(fs.readFileSync(path.join(BUILD, 'sheet_clip_dims_jpg.json')));

const OMIT_NUMBERS = (process.env.OMIT_NUMBERS || '')
  .split(',').map(s => parseInt(s.trim(), 10)).filter(Number.isFinite);
const totalLogged = masterFull.length;
const master = masterFull.filter(m => !OMIT_NUMBERS.includes(m.number));
if (OMIT_NUMBERS.length) {
  console.log(`omitting ${OMIT_NUMBERS.length} item(s): ${OMIT_NUMBERS.join(', ')}`);
}

const PAGE_W = 12240, PAGE_H = 15840, MARGIN = 1080;
const USABLE_W = PAGE_W - 2 * MARGIN;
const USABLE_H = (PAGE_H - 2 * (MARGIN + 200)) - 500;

const BLUE = '666F89';
const DARKGREY = '58595B';
const LIGHTGREY = 'A6A6A5';
const GREEN = '3C7D7F';
const BLUE_TINT = 'E7E9EE';
const ALERT_RED = 'B00000';
const FONT = 'Arial';

const LOGO_WHITE = fs.readFileSync(path.join(BUILD, 'assets/logos/EPlus-Logo-White.png'));
const ICON_BLUE = fs.readFileSync(path.join(BUILD, 'assets/logos/EPlus-Icon.png'));

// Meta-table column layout: label | value | sheet-clip image (rowSpan across all 4 rows)
const META_LABEL_W = 1750;
const CLIP_COL_W = 2450;
const META_VALUE_W = USABLE_W - META_LABEL_W - CLIP_COL_W;
const CLIP_IMG_W = CLIP_COL_W - 240; // inner padding allowance

function fmtTimestamp(title) {
  const m = title.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
  if (!m) return title;
  const [, yyyy, mm, dd, HH, MM] = m;
  return `${mm}/${dd}/${yyyy} ${HH}:${MM}`;
}

function run(text, opts = {}) {
  return new TextRun({ text, font: FONT, ...opts });
}

function estimateTextHeightDXA(text, sizeHalfPt, widthDXA) {
  if (!text) return 0;
  const pt = sizeHalfPt / 2;
  const usableWidthPt = widthDXA / 20;
  const charsPerLine = Math.max(15, Math.floor(usableWidthPt / (0.5 * pt)));
  const lines = Math.max(1, Math.ceil(text.length / charsPerLine));
  const lineHeightDXA = Math.round(pt * 23);
  return lines * lineHeightDXA;
}

function clipHeightForItem(item) {
  const base = path.basename(item.sheetClipPath || '');
  const [w, h] = clipDims[base] || [800, 800];
  return Math.round(CLIP_IMG_W * (h / w));
}

function estimateOverheadDXA(item) {
  let h = 0;
  h += 360; // "Item #N" heading line

  // Meta table height = max(the 4 text rows, the sheet-clip image), since the clip sits in a
  // rowSpan cell alongside them rather than adding its own separate block.
  const rowsData = [
    item.location || 'Not specified in source data — see sheet reference and photos',
    `${item.sheet_name || '—'}${item.sheet_description ? ' (' + item.sheet_description + ')' : ''}`,
    (item.status || 'open').toUpperCase(),
    item.confidence,
  ];
  const textRowsHeight = rowsData.reduce((sum, v) => sum + estimateTextHeightDXA(String(v), 19, META_VALUE_W) + 100, 0);
  const clipH = clipHeightForItem(item) + 120;
  h += Math.max(textRowsHeight, clipH) + 60;

  h += 340; // "Deficiency Description" label
  h += estimateTextHeightDXA(item.description || '', 21, USABLE_W) + 100;
  if (item.origin === 'jim_described' && item.jim_original_text) {
    h += estimateTextHeightDXA(`Field engineer's original note: "${item.jim_original_text}"`, 18, USABLE_W) + 60;
  }
  if (item.cross_ref) {
    h += estimateTextHeightDXA(`Cross-reference to walk notes: ${item.cross_ref}`, 18, USABLE_W) + 60;
  }
  if (item.precedent_note) {
    h += estimateTextHeightDXA(`EPLUS precedent check: ${item.precedent_note}`, 18, USABLE_W) + 60;
  }
  if (item.reviewer_flag) {
    h += estimateTextHeightDXA(`REVIEWER FLAG: ${item.reviewer_flag}`, 19, USABLE_W) + 100;
  }
  h += 320; // "Photos (n)" label
  h += 420; // bottom divider paragraph before/after spacing
  return h;
}

function layoutForItem(item) {
  const n = item.photo_paths.length;
  const remaining = USABLE_H - estimateOverheadDXA(item);
  const origDims = item.photo_paths.map(p => dims[path.basename(p)] || [700, 525]);
  const avgAspect = origDims.reduce((s, [w, h]) => s + h / w, 0) / origDims.length;
  const ROW_OVERHEAD = 320;

  if (n === 1) {
    const w = Math.min(4600, USABLE_W) - 200;
    return { cols: 1, imgWidthDXA: w };
  }
  if (n === 2) {
    const w = Math.min(4200, Math.floor(USABLE_W / 2)) - 200;
    return { cols: 2, imgWidthDXA: w };
  }

  const MIN_W = 900;
  let best = null;
  for (let cols = 3; cols <= 8; cols++) {
    const colW = Math.floor(USABLE_W / cols) - 200;
    const rowH = colW * avgAspect + ROW_OVERHEAD;
    const rows = Math.ceil(n / cols);
    const total = rows * rowH;
    if (total <= Math.max(remaining, 0) && colW >= MIN_W) {
      best = { cols, imgWidthDXA: colW };
      break;
    }
  }
  if (!best) {
    const cols = 8;
    const rows = Math.ceil(n / cols);
    const neededW = Math.floor((Math.max(remaining, 1) / rows - ROW_OVERHEAD) / avgAspect);
    const colW = Math.max(MIN_W, Math.min(neededW, Math.floor(USABLE_W / cols) - 200));
    best = { cols, imgWidthDXA: colW, tight: true };
  }
  return best;
}

function photoGrid(item, layout) {
  const paths = item.photo_paths.map(p => path.join(BUILD, 'thumbs', path.basename(p)));
  const titles = item.photo_titles;
  const { cols, imgWidthDXA } = layout;
  const colWidthDXA = Math.floor(USABLE_W / cols);
  const targetPxW = Math.floor((imgWidthDXA / 1440) * 96);

  const cells = paths.map((p, i) => {
    const base = path.basename(p);
    const [origW, origH] = dims[base] || [700, 525];
    const w = targetPxW;
    const h = Math.round(origH * (w / origW));
    let imgChildren;
    try {
      const data = fs.readFileSync(p);
      imgChildren = [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new ImageRun({ type: 'jpg', data, transformation: { width: w, height: h } })],
        }),
      ];
    } catch (e) {
      imgChildren = [new Paragraph({ children: [run('[image unavailable]', { italics: true, size: 16 })] })];
    }
    imgChildren.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [run(fmtTimestamp(titles[i] || ''), { size: 13, color: LIGHTGREY })],
    }));
    return new TableCell({
      width: { size: colWidthDXA, type: WidthType.DXA },
      margins: { top: 40, bottom: 40, left: 40, right: 40 },
      borders: noBorders(),
      children: imgChildren,
    });
  });

  const rows = [];
  for (let i = 0; i < cells.length; i += cols) {
    let rowCells = cells.slice(i, i + cols);
    while (rowCells.length < cols) {
      rowCells.push(new TableCell({
        width: { size: colWidthDXA, type: WidthType.DXA },
        borders: noBorders(),
        children: [new Paragraph({ text: '' })],
      }));
    }
    rows.push(new TableRow({ cantSplit: true, children: rowCells }));
  }
  return new Table({
    width: { size: USABLE_W, type: WidthType.DXA },
    columnWidths: Array(cols).fill(colWidthDXA),
    rows,
  });
}

function noBorders() {
  const none = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
  return { top: none, bottom: none, left: none, right: none };
}

function thinBorders(color = LIGHTGREY) {
  const b = { style: BorderStyle.SINGLE, size: 4, color };
  return { top: b, bottom: b, left: b, right: b };
}

function metaTable(item) {
  const rowsData = [
    ['Location', item.location || 'Not specified in source data — see sheet reference and photos'],
    ['Drawing Sheet', `${item.sheet_name || '—'}${item.sheet_description ? ' (' + item.sheet_description + ')' : ''}`],
    ['Status', (item.status || 'open').toUpperCase()],
    ['Confidence / Source', item.confidence],
  ];

  // Sheet-clip cell: the PlanGrid drawing snip (sheet + red pin stamp) for this item,
  // spanning all 4 rows so it sits alongside the whole meta block rather than adding height.
  let clipCellChildren;
  if (item.sheetClipPath && fs.existsSync(item.sheetClipPath)) {
    const base = path.basename(item.sheetClipPath);
    const [cw, ch] = clipDims[base] || [800, 800];
    const w = Math.floor((CLIP_IMG_W / 1440) * 96); // DXA -> px, same conversion photoGrid uses
    const h = Math.round(w * (ch / cw));
    const data = fs.readFileSync(item.sheetClipPath);
    clipCellChildren = [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new ImageRun({ type: 'jpg', data, transformation: { width: w, height: h } })],
      }),
    ];
  } else {
    clipCellChildren = [new Paragraph({ children: [run('Sheet snip unavailable', { italics: true, size: 14, color: LIGHTGREY })] })];
  }

  const rows = rowsData.map(([k, v], i) => {
    const children = [
      new TableCell({
        width: { size: META_LABEL_W, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, color: 'auto', fill: BLUE_TINT },
        margins: { top: 50, bottom: 50, left: 100, right: 100 },
        borders: thinBorders(),
        children: [new Paragraph({ children: [run(k, { bold: true, size: 19, color: BLUE })] })],
      }),
      new TableCell({
        width: { size: META_VALUE_W, type: WidthType.DXA },
        margins: { top: 50, bottom: 50, left: 100, right: 100 },
        borders: thinBorders(),
        children: [new Paragraph({ children: [run(String(v), { size: 19, color: DARKGREY })] })],
      }),
    ];
    if (i === 0) {
      // docx auto-generates the vertical-merge continuation cells for the rows below -
      // do not add a third cell manually on i>0 rows, or the column will get double cells.
      children.push(new TableCell({
        width: { size: CLIP_COL_W, type: WidthType.DXA },
        rowSpan: rowsData.length,
        verticalAlign: VerticalAlign.CENTER,
        margins: { top: 60, bottom: 60, left: 60, right: 60 },
        borders: thinBorders(),
        children: clipCellChildren,
      }));
    }
    return new TableRow({ cantSplit: true, children });
  });
  return new Table({ width: { size: USABLE_W, type: WidthType.DXA }, columnWidths: [META_LABEL_W, META_VALUE_W, CLIP_COL_W], rows });
}

function itemSection(item) {
  const layout = layoutForItem(item);
  const children = [];
  children.push(new Paragraph({
    heading: HeadingLevel.HEADING_2,
    pageBreakBefore: true,
    keepNext: true,
    spacing: { before: 0, after: 90 },
    children: [
      run(`Item #${item.number}`, { bold: true, size: 26, color: BLUE }),
      run(
        item.origin === 'jim_described' ? '' : '  [Draft — see confidence/reviewer note]',
        { italics: true, size: 18, color: item.origin === 'undeterminable' ? ALERT_RED : BLUE }
      ),
    ],
  }));
  children.push(metaTable(item));
  children.push(new Paragraph({ text: '', spacing: { after: 60 }, keepNext: true }));
  children.push(new Paragraph({
    keepNext: true,
    keepLines: true,
    children: [run('Deficiency Description', { bold: true, size: 21, color: BLUE })],
    spacing: { after: 50 },
  }));
  children.push(new Paragraph({
    keepNext: true,
    keepLines: true,
    children: [run(item.description || '(no description available)', { size: 20, color: DARKGREY })],
    spacing: { after: 80 },
  }));

  if (item.origin === 'jim_described' && item.jim_original_text) {
    children.push(new Paragraph({
      keepNext: true, keepLines: true,
      spacing: { after: 50 },
      children: [
        run("Field engineer's original note: ", { italics: true, bold: true, size: 18, color: DARKGREY }),
        run(`"${item.jim_original_text}"`, { italics: true, size: 18, color: DARKGREY }),
      ],
    }));
  }
  if (item.cross_ref) {
    children.push(new Paragraph({
      keepNext: true, keepLines: true,
      spacing: { after: 50 },
      children: [
        run('Cross-reference to walk notes: ', { bold: true, size: 18, color: BLUE }),
        run(item.cross_ref, { size: 18, color: BLUE }),
      ],
    }));
  }
  if (item.precedent_note) {
    children.push(new Paragraph({
      keepNext: true, keepLines: true,
      spacing: { after: 50 },
      children: [
        run('EPLUS precedent check: ', { bold: true, italics: true, size: 18, color: DARKGREY }),
        run(item.precedent_note, { italics: true, size: 18, color: DARKGREY }),
      ],
    }));
  }
  if (item.reviewer_flag) {
    children.push(new Paragraph({
      keepNext: true, keepLines: true,
      spacing: { after: 80 },
      children: [
        run('⚑ REVIEWER FLAG: ', { bold: true, size: 19, color: ALERT_RED }),
        run(item.reviewer_flag, { size: 19, color: ALERT_RED }),
      ],
    }));
  }

  children.push(new Paragraph({
    keepNext: true,
    children: [run(`Photos (${item.photo_paths.length})`, { bold: true, size: 20, color: BLUE })],
    spacing: { after: 50 },
  }));
  children.push(photoGrid(item, layout));
  children.push(new Paragraph({
    spacing: { before: 160, after: 0 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: LIGHTGREY, space: 1 } },
    children: [run('')],
  }));
  return { children, layout };
}

// Attach each item's sheet-clip path
for (const item of master) {
  item.sheetClipPath = path.join(BUILD, 'sheet_clips_jpg', `item_${item.number}.jpg`);
}

const describedCount = master.filter(m => m.origin === 'jim_described').length;
const photoOnlyCount = master.length - describedCount;
const undeterminable = master.filter(m => m.origin === 'undeterminable').length;
const proposed = photoOnlyCount - undeterminable;

const coverBanner = new Table({
  width: { size: USABLE_W, type: WidthType.DXA },
  columnWidths: [USABLE_W],
  rows: [
    new TableRow({
      children: [
        new TableCell({
          width: { size: USABLE_W, type: WidthType.DXA },
          shading: { type: ShadingType.CLEAR, color: 'auto', fill: BLUE },
          margins: { top: 260, bottom: 260, left: 260, right: 260 },
          borders: {
            top: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
            left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
            right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
            bottom: { style: BorderStyle.SINGLE, size: 18, color: GREEN },
          },
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [new ImageRun({ type: 'png', data: LOGO_WHITE, transformation: { width: 350, height: 70 } })],
            }),
          ],
        }),
      ],
    }),
  ],
});

const cover = [
  coverBanner,
  new Paragraph({ spacing: { before: 280 }, children: [run('')] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [run('DRAFT — FOR INTERNAL REVIEW ONLY', { bold: true, color: ALERT_RED, size: 26 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 80 },
    children: [run('Not for issuance to Owner, GC, or Subcontractors until reviewed and edited by Victor Ortega', { italics: true, size: 18, color: DARKGREY })],
  }),
  new Paragraph({ spacing: { before: 220 }, children: [run('')] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [run('NVA06B-PUNCH', { bold: true, size: 48, color: BLUE })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80 },
    children: [run('Punch Report — Site Walk', { size: 28, color: DARKGREY })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 40, after: 220 },
    children: [run('August 13, 2026', { size: 24, color: DARKGREY })],
  }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [run('Leesburg, Virginia', { size: 20, color: DARKGREY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 160 }, children: [run('Prepared by: Jim McGlynn, Engineering PLUS (EPLUS Advisors)', { size: 20, color: DARKGREY })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 40 }, children: [run('Draft compiled: August 17, 2026', { size: 20, color: DARKGREY })] }),
  new Paragraph({ spacing: { before: 260 }, children: [run('')] }),
  new Paragraph({
    children: [run('SUMMARY', { bold: true, size: 22, color: BLUE })],
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: BLUE, space: 2 } },
    spacing: { after: 90 },
  }),
  new Paragraph({ spacing: { before: 60, after: 45 }, children: [run(`This report covers ${totalLogged} punch items logged during the August 13, 2026 site walk of NVA06B, pulled directly from the project's PlanGrid punch list. ${master.length} are documented below — items #1 and #2 have been omitted (each was a single photo of a field team member in the site office trailer, with no field condition documented; see Lessons Learned).`, { size: 19, color: DARKGREY })] }),
  new Paragraph({ spacing: { after: 45 }, children: [run(`• ${describedCount} items carry a written deficiency description from field engineer Jim McGlynn. His wording has been lightly polished into report voice below; his original note is quoted alongside each for traceability.`, { size: 19, color: DARKGREY })] }),
  new Paragraph({ spacing: { after: 45 }, children: [run(`• ${photoOnlyCount} items were logged as photo-only pins with no written description. Of these, ${proposed} were cross-referenced against Jim's separate walk-notes document and/or the site photos to propose a draft description (flagged "Draft" and hedged by confidence level below). The remaining ${undeterminable} had photos that were too ambiguous, obstructed, or generic to support any specific deficiency claim — these are marked "not determinable from available data" rather than guessed at.`, { size: 19, color: DARKGREY })] }),
  new Paragraph({ spacing: { after: 45 }, children: [run(`• All ${master.length} items carry at least one site photo, plus a drawing snip showing the sheet reference and pin location.`, { size: 19, color: DARKGREY })] }),
  new Paragraph({ spacing: { after: 140 }, children: [run('• Drawing sheets referenced: T-R-100 (Site), T-R-101 (1st Floor), T-R-102 (2nd Floor).', { size: 19, color: DARKGREY })] }),
  new Paragraph({
    spacing: { after: 45 },
    children: [run('Precedent lookup note: ', { bold: true, size: 19, color: DARKGREY }), run('the EPLUS historical punch database was unreachable earlier in this session and a first pass of this report was issued without it (see prior draft). That connector is now working; a precedent pass has been completed against NVA05A, NVA05D, and CHI01A for the recurring themes called out in the brief (bushings, grounding, J-hooks, labeling, zip ties). Matches and gaps are noted inline as "EPLUS precedent check" under the relevant items — most notably, no corpus precedent was found for treating zip ties or a specific J-hook spacing citation as a deficiency in their own right, which is worth confirming with Jim directly.', { size: 19, color: DARKGREY })],
  }),
  new Paragraph({
    children: [run('How to read each entry: ', { bold: true, size: 19, color: DARKGREY }), run('items with a field-engineer description are marked "high (field-engineer authored)" confidence. Draft photo-based items show high/medium/low confidence and a source tag. Any item with a ⚑ REVIEWER FLAG needs a specific check before issuance.', { size: 19, color: DARKGREY })],
  }),
];

const children = [...cover];
const tightItems = [];
for (const item of master) {
  const { children: sectionChildren, layout } = itemSection(item);
  children.push(...sectionChildren);
  if (layout.tight) tightItems.push(item.number);
}

if (tightItems.length) {
  console.log('Items that needed the densest photo grid (may still run slightly long):', tightItems.join(', '));
}

const header = new Header({
  children: [
    new Table({
      width: { size: USABLE_W, type: WidthType.DXA },
      columnWidths: [1000, USABLE_W - 1000],
      rows: [
        new TableRow({
          children: [
            new TableCell({
              width: { size: 1000, type: WidthType.DXA },
              verticalAlign: VerticalAlign.CENTER,
              borders: { ...noBorders(), bottom: { style: BorderStyle.SINGLE, size: 10, color: GREEN } },
              children: [new Paragraph({ children: [new ImageRun({ type: 'png', data: ICON_BLUE, transformation: { width: 28, height: 20 } })] })],
            }),
            new TableCell({
              width: { size: USABLE_W - 1000, type: WidthType.DXA },
              verticalAlign: VerticalAlign.CENTER,
              borders: { ...noBorders(), bottom: { style: BorderStyle.SINGLE, size: 10, color: GREEN } },
              children: [new Paragraph({
                alignment: AlignmentType.RIGHT,
                children: [run('NVA06B-PUNCH — DRAFT REPORT', { size: 16, color: BLUE, bold: true })],
              })],
            }),
          ],
        }),
      ],
    }),
  ],
});

const footer = new Footer({
  children: [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      border: { top: { style: BorderStyle.SINGLE, size: 4, color: LIGHTGREY, space: 4 } },
      children: [
        run('Engineering PLUS  •  NVA06B-PUNCH Draft Report  •  Page ', { size: 14, color: LIGHTGREY }),
        new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 14, color: LIGHTGREY }),
        run(' of ', { size: 14, color: LIGHTGREY }),
        new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: 14, color: LIGHTGREY }),
      ],
    }),
  ],
});

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: FONT, color: DARKGREY, size: 21 } },
    },
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: { top: MARGIN + 200, bottom: MARGIN + 200, left: MARGIN, right: MARGIN },
        },
      },
      headers: { default: header },
      footers: { default: footer },
      children,
    },
  ],
});

Packer.toBuffer(doc).then(buf => {
  // Never overwrite in place: scratch workspaces routinely refuse it
  // ("Operation not permitted") and some libraries unlink-then-write.
  let out = OUT_FILE;
  for (let n = 2; fs.existsSync(out); n++) {
    out = OUT_FILE.replace(/\.docx$/, `-v${n}.docx`);
  }
  fs.writeFileSync(out, buf);
  console.log('wrote', out, buf.length, 'bytes');
});
