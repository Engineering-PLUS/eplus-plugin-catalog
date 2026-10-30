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
| `eplus-branding` | EPLUS brand guidelines (colors, logos, typography) using portable system fonts — for deliverables that must survive PDF round-trips and cross-app editing |
| `workflow-packager` | Detects document-heavy conversations and, after completing the task, offers to package the prompt and reference documents into a reusable personal skill |
| `eplus-getting-started` | Onboarding tour ("show me what you can do"): short hands-on demos of the Claude desktop app itself: connecting the user's accounts (Microsoft 365 profile, with the connectors-and-updates video shipped in `assets/videos/` for a first-time sign-in), the user's getting-started page, handed over as a file they open in their own web browser (what to ask for, a map of every connector and its tools by who built it, the / menu, and a card per demo tried), memory, making a skill, a branded Word document, the browser (EPLUS model viewer, in its own tab beside the page), building a LibreChat agent, a scheduled task, and finding a training video in the EPLUS University library (`epu-video-library` connector). One file per demo under `demos/`; the page is built by `scripts/build_page.py` from `assets/getting-started.html`, `assets/cheatsheet-content.json` (capabilities, / menu, help) and `assets/connectors.json` (connectors, their tools, which tools write, and the skills that use each one), which are updated when skills or connectors change; connector icons live in `assets/connector-icons/` |
| `epu` | `/epu`: opens the EPLUS University video library browser at its root, with no text around it. Needs the `epu-video-library` connector. |

`eplus-branding` carries its brand summary, logo assets, and
the Brand Guidelines PDF inside the skill folder. `workflow-packager` and
`eplus-getting-started` have no server dependency; `eplus-getting-started` uses only
the app's built-in tools (the browser, memory, save_skill, scheduled tasks)
plus `eplus-branding`. `epu` and the tour's video demo call the
`epu-video-library` managed connector and do nothing without it. Nothing in this
plugin needs a local process.

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
`eplus-branding` should load. For the packager, attach 3+
office files with a structured prompt and confirm the workflow-packaging
offer appears after the task is delivered.
