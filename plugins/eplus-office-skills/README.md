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
| `eplus-branding-default-fonts` | EPLUS brand guidelines (colors, logos, typography) using portable system fonts — for deliverables that must survive PDF round-trips and cross-app editing |
| `workflow-packager` | Detects document-heavy conversations and, after completing the task, offers to package the prompt and reference documents into a reusable personal skill |

The four document skills are copied verbatim from the upstream repo,
including their `LICENSE.txt` and bundled scripts. Do not hand-edit the
vendored content — re-vendor from upstream instead (see below).
`eplus-branding-default-fonts` is EPLUS-authored (brand summary, logo
assets, and the Brand Guidelines PDF live inside the skill folder) and is
maintained here directly. `workflow-packager` is also EPLUS-authored and
has no server dependency. Nothing in this plugin needs a server or a
local process: all PDF work — creation, merging, splitting, form fill,
annotation via markup — goes through the vendored Anthropic `pdf` skill.
(An earlier version bundled a `view-pdf` skill backed by a local stdio
MCP viewer; it was removed because local processes cannot run in the
Cowork VM.)

**Not included:** `file-reading` and `pdf-reading` (the upload-routing and
PDF-extraction strategy skills seen in consumer Chat) are internal
Anthropic skills that are not in the public repo, so they cannot be
vendored.

## Updating from upstream

1. Clone `https://github.com/anthropics/skills` (on Windows set
   `git config core.longpaths true` first — the OOXML schema paths exceed
   MAX_PATH).
2. Replace `skills/<name>` here with the upstream `skills/<name>` folder.
3. Re-apply local patches: `docx/SKILL.md` softens upstream's "`docx` is
   preinstalled" claim — Cowork VMs were observed without it.
4. Bump `version` in `.claude-plugin/plugin.json` — machines only receive
   the update on a version bump.

## Installation

**This plugin is a required install for the Cowork fleet.** The fleet is
Cowork-only (Claude Code CLI is disabled), so distribution goes through
the claude.ai admin console, not managed settings:

1. Go to [Organization settings > Plugins](https://claude.ai/admin-settings/plugins)
   (Owner/Primary Owner, Team/Enterprise plan; Cowork and Skills must be
   enabled).
2. Connect this repository as a GitHub-synced marketplace (repo must stay
   private/internal; the Claude GitHub App handles sync).
3. Set this plugin's installation preference to **Required** — it
   auto-installs for all org members and cannot be disabled or
   uninstalled.

**Sync behavior:** automatic sync runs only when a PR containing a plugin
**version bump** merges to the default branch. Direct pushes do not
trigger a sync — bump `version` in `.claude-plugin/plugin.json` in every
release PR, or trigger manually via "Update" on the marketplace.

Verify by asking Claude to create a small .docx or .xlsx — the matching
skill should fire on its own. For branding, ask Claude to "style this
deck with EPLUS branding" — `eplus-branding-default-fonts` should load.
For PDF work, ask Claude to fill a form or merge two PDFs — the `pdf`
skill should fire. For the packager, attach 3+ office files with a
structured prompt and confirm the workflow-packaging offer appears
after the task is delivered.
