# eplus-office-skills

Anthropic's official document skills, vendored from
[anthropics/skills](https://github.com/anthropics/skills) and delivered to
the EPLUS Chat/Cowork fleet through this catalog. The consumer Claude
subscription bundles these server-side; a 3P deployment gets only what its
config declares, so this plugin closes that gap.

## Skills

| Skill | Purpose |
|-------|---------|
| `docx` | Create/edit Word documents and templates (tracked changes, comments, formatting) |
| `pdf`  | Create, merge, split, fill forms, encrypt/decrypt PDFs |
| `pptx` | Create/edit PowerPoint decks and templates |
| `xlsx` | Create/edit spreadsheets (.xlsx, .xlsm, .csv, .tsv), formulas, cleaning |

Each skill folder is copied verbatim from the upstream repo, including its
`LICENSE.txt` and bundled scripts. Do not hand-edit the vendored content —
re-vendor from upstream instead (see below).

**Not included:** `file-reading` and `pdf-reading` (the upload-routing and
PDF-extraction strategy skills seen in consumer Chat) are internal
Anthropic skills that are not in the public repo, so they cannot be
vendored.

## Updating from upstream

1. Clone `https://github.com/anthropics/skills` (on Windows set
   `git config core.longpaths true` first — the OOXML schema paths exceed
   MAX_PATH).
2. Replace `skills/<name>` here with the upstream `skills/<name>` folder.
3. Bump `version` in `.claude-plugin/plugin.json` — machines only receive
   the update on a version bump.

## Installation

```bash
claude plugin install eplus-office-skills@eplus-claude-plugins
```

Verify by asking Claude to create a small .docx or .xlsx — the matching
skill should fire on its own.
