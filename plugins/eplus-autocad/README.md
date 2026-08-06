# eplus-autocad

Bundles the [autocad-mcp](https://github.com/Engineering-PLUS/autocad-mcp)
server together with the skill and hooks that teach Claude the EPLUS CAD
workflow, so tools, doctrine, and guardrails always ship as one unit.

## Contents

| Component | Path | Purpose |
|-----------|------|---------|
| Manifest  | [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) | Plugin identity and metadata |
| MCP       | [`.mcp.json`](.mcp.json) | Launches the `autocad` stdio server when the plugin is enabled |
| Skill     | [`skills/cad-workflow/SKILL.md`](skills/cad-workflow/SKILL.md) | Umbrella: three-lane doctrine, clone rules, tool selection guide |
| Skills    | [`skills/`](skills/) | One skill per MCP tool (9 total) so the model reliably reaches for the right tool and reports failures instead of improvising: `get-cad-status`, `check-cad-installation`, `inspect-drawing`, `analyze-size-distribution`, `inspect-entities`, `render-view`, `capture-session-view`, `select-in-session`, `open-for-editing` |
| Hooks     | [`hooks/hooks.json`](hooks/hooks.json) | `SessionStart` context; `PreToolUse` ask-gate on the two session-touching tools |

Every per-tool skill ends with the same failure protocol: if the `autocad`
connector is missing or the call errors, the model tells the user exactly
that (with the real error) instead of silently skipping or fabricating
results. The MCP server itself is expected to be delivered outside the
plugin (managed/direct connector); the bundled `.mcp.json` is a fallback.

## Tool naming

Plugin-bundled server tools are scoped as
`mcp__plugin_eplus-autocad_autocad__<tool>`. The fleet's managed connector
exposes the same server as `mcp__autocad__<tool>`. The skill references
tools by bare name and the hook matcher is a regex covering **both**
prefixes — keep it that way when adding hooks:

```
^mcp__(plugin_eplus-autocad_)?autocad__(select_in_session|open_for_editing)$
```

## MCP wiring

[`.mcp.json`](.mcp.json) launches the server with the same `cmd.exe`-wrapped
`uvx` command the fleet bootstrap uses (see the server repo's
`DEPLOYMENT.md`): pinned tag, read-only PAT in the `--from` URL. Machine
prerequisites are the same as the fleet's: `uv` at `C:\Program Files\uv`,
`git` on PATH, and github.com reachable on first run.

The PAT is supplied via env-var expansion: each machine sets
`AUTOCAD_MCP_PAT` (provisioned by the deployment utility, not handed to
users) to a fine-grained token scoped to only the `autocad-mcp` repo with
Contents: Read — it grants nothing but the ability to fetch that code. No
token is committed to this repo. Rotate by updating the env var on each
machine.

Versioning is explicit: bump `version` in `plugin.json` whenever a change
should reach installed machines — pushing commits alone does nothing once
a version is pinned. When shipping a server update, bump `@v0.X.Y` in
`.mcp.json` **and** the fleet bootstrap config in the same change, plus
the plugin version.

Plugin `.mcp.json` does not support `toolPolicy` or `startupTimeoutSec` —
those live in the Desktop managed config. Here, the session-touching gate is
enforced by the `PreToolUse` hook instead.

## Known caveats

- **Windows hosts only.** The server needs Win32 COM and AutoCAD; the
  bundled `.mcp.json` cannot work inside Cowork's Linux VM. Cowork fleet
  machines get the server via the managed connector instead; this plugin's
  skill and hooks still apply there. Deliberately deferred for now.
- **Duplicate server risk:** if a machine also has a user-level or managed
  connector for the same server (e.g. `civil3d` or `autocad`), enabling
  this plugin runs a second copy. Harmless for reads, but pick one wiring
  per machine when you notice doubled tools.
- **Collision behavior unverified:** whether the managed `autocad`
  connector blocks the plugin-scoped copy (or vice versa) has not been
  tested on a fleet machine.

## Installation

From the `eplus-claude-plugins` marketplace:

```bash
claude plugin install eplus-autocad@eplus-claude-plugins
```

Verify with `/mcp` (server `autocad` connected, 9 tools) and by asking
*"What's the status of my CAD session?"*.
