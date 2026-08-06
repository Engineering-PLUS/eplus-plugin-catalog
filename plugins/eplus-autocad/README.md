# eplus-autocad

Bundles the [autocad-mcp](https://github.com/Engineering-PLUS/autocad-mcp)
server together with the skill and hooks that teach Claude the EPLUS CAD
workflow, so tools, doctrine, and guardrails always ship as one unit.

## Contents

| Component | Path | Purpose |
|-----------|------|---------|
| Manifest  | [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) | Plugin identity and metadata |
| MCP       | [`.mcp.json`](.mcp.json) | Launches the `autocad` stdio server when the plugin is enabled |
| Skill     | [`skills/cad-workflow/SKILL.md`](skills/cad-workflow/SKILL.md) | Three-lane doctrine, clone rules, tool selection guide |
| Hooks     | [`hooks/hooks.json`](hooks/hooks.json) | `SessionStart` context; `PreToolUse` ask-gate on the two session-touching tools |

## Tool naming

Plugin-bundled server tools are scoped as
`mcp__plugin_eplus-autocad_autocad__<tool>`. The fleet's managed connector
exposes the same server as `mcp__autocad__<tool>`. The skill references
tools by bare name and the hook matcher is a regex covering **both**
prefixes — keep it that way when adding hooks:

```
^mcp__(plugin_eplus-autocad_)?autocad__(select_in_session|open_for_editing)$
```

## MCP wiring — current state and target state

**Current (dev, this machine only):** [`.mcp.json`](.mcp.json) points at the
local venv of the server checkout
(`...\AutoCAD\civil-3d-mcp\.venv\Scripts\python.exe -m autocad_mcp`). It
works immediately on Victor's workstation and nowhere else.

**Target (portable):** swap the command for the same `cmd.exe`-wrapped
`uvx` launch the fleet bootstrap uses (see the server repo's
`DEPLOYMENT.md`), with the read-only PAT supplied via env-var expansion —
**never commit a literal PAT to this repo**:

```json
{
  "autocad": {
    "command": "C:\\Windows\\System32\\cmd.exe",
    "args": [
      "/c", "C:\\Program Files\\uv\\uvx.exe",
      "--python", "3.12",
      "--from", "git+https://x-access-token:${AUTOCAD_MCP_PAT}@github.com/Engineering-PLUS/autocad-mcp@v0.2.0",
      "autocad-mcp"
    ]
  }
}
```

When shipping a server update, bump the pinned tag here **and** in the
fleet bootstrap config in the same change.

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
