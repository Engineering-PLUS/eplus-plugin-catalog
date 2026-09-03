# eplus-office-skills

EPLUS-authored document skills for the Cowork/Chat fleet, delivered through
this catalog.

Anthropic's `docx`, `pdf`, `pptx`, and `xlsx` skills used to be vendored here.
Anthropic now ships those natively in Cowork and Chat, so the vendored copies
were removed; keeping them only duplicated what every seat already has. If a
seat ever lacks them, re-vendor from
[anthropics/skills](https://github.com/anthropics/skills) rather than
hand-writing replacements.

## Skills

| Skill | Purpose |
|-------|---------|
| `eplus-branding-default-fonts` | EPLUS brand guidelines (colors, logos, typography) using portable system fonts — for deliverables that must survive PDF round-trips and cross-app editing |
| `workflow-packager` | Detects document-heavy conversations and, after completing the task, offers to package the prompt and reference documents into a reusable personal skill |

`eplus-branding-default-fonts` carries its brand summary, logo assets, and
the Brand Guidelines PDF inside the skill folder. `workflow-packager` has no
server dependency. Nothing in this plugin needs a server or a local process.

**Not included:** `file-reading` and `pdf-reading` (the upload-routing and
PDF-extraction strategy skills seen in consumer Chat) are internal
Anthropic skills that are not in the public repo, so they cannot be
vendored.

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

Verify by asking Claude to "style this deck with EPLUS branding" —
`eplus-branding-default-fonts` should load. For the packager, attach 3+
office files with a structured prompt and confirm the workflow-packaging
offer appears after the task is delivered.
