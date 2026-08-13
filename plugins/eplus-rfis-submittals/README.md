# eplus-rfis-submittals

Skill that teaches Claude the EPLUS RFI & Submittal
Processing workflow. The backend is the **Hermes Knowledge Engine** — a
dedicated Azure VM running a FastMCP server over HTTP/SSE with native
file access to 82,000+ pages of extracted AEC technical documents (Core &
Shell specs, TFO documentation, product submittals, historical RFIs, and
TIA/NEC codebooks) indexed via Graphify (Graph-RAG).

Unlike `eplus-autocad` (whose server is a **local** stdio process that
cannot run inside the Cowork VM), Hermes is a **remote** SSE server —
safe to bundle. This plugin ships an `.mcp.json` at the plugin root that
connects directly over SSE with a Bearer auth header; no local process
is launched, so it works in Claude Code, Cowork, and managed fleets
alike. For Claude Desktop (which does not read plugin `.mcp.json`), use
the `npx supergateway` snippet below in `claude_desktop_config.json`.

## Contents

| Component | Path | Purpose |
|-----------|------|---------|
| Manifest  | [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json) | Plugin identity and metadata |
| Skill     | [`skills/rfi/SKILL.md`](skills/rfi/SKILL.md) | 4-step doctrine: deconstruct → query Hermes → draft → HITL write-back gate, plus the return path for logging final RFI responses issued outside the chat |
| MCP       | [`.mcp.json`](.mcp.json) | Bundled remote SSE connection to the Hermes VM with Bearer auth |

## MCP tools (server name: `eplus-rfi-engine`)

1. `query_hermes_rfi(query: str, project_id: str = "default", csi_section: Optional[str] = None) -> str`
   — dispatches a search query to the Hermes Graph-RAG engine and returns
   a synthesized context report.
2. `commit_approved_rfi(rfi_id: str, markdown_content: str, metadata: dict, project_id: str = "default") -> dict`
   — writes back human-approved final RFI responses to the VM database
   and triggers an incremental background update to the knowledge graph.
   Gated behind explicit user approval by the skill.

## Claude Code / Cowork configuration

Bundled in [`.mcp.json`](.mcp.json) — native remote SSE, no local
process (replace `<AZURE_VM_PUBLIC_IP>` with the Hermes VM's public IP):

```json
{
  "mcpServers": {
    "eplus-rfi-engine": {
      "type": "sse",
      "url": "http://<AZURE_VM_PUBLIC_IP>:8650/sse",
      "headers": {
        "Authorization": "Bearer af19f84270b9b2ff993fa7246c08067d84188ac01ae4fa4134c695ba4aa36de7"
      }
    }
  }
}
```

## Claude Desktop configuration

Claude Desktop doesn't load plugin `.mcp.json`; for local testing there,
add the supergateway proxy to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "eplus-rfi-engine": {
      "command": "npx",
      "args": [
        "-y",
        "supergateway",
        "--sse",
        "http://<AZURE_VM_PUBLIC_IP>:8650/sse",
        "--header",
        "Authorization: Bearer af19f84270b9b2ff993fa7246c08067d84188ac01ae4fa4134c695ba4aa36de7"
      ]
    }
  }
}
```

> **Security note:** the bearer token above is a shared static credential
> sent over plain HTTP. Rotate it if it leaks, and prefer fronting the VM
> with HTTPS (or an Azure Application Gateway/TLS terminator) before
> wide deployment.

## Tool naming

The bundled server is named `eplus-rfi-engine`, so tools appear as
`mcp__plugin_eplus-rfis-submittals_eplus-rfi-engine__<tool>` when loaded
from this plugin, or `mcp__eplus-rfi-engine__<tool>` from a
desktop/managed connection. The skill tolerates both.

## Versioning

Explicit semver in `plugin.json` — bump `version` whenever a change
should reach installed machines.

## Installation

From the `eplus-claude-plugins` marketplace:

```bash
claude plugin install eplus-rfis-submittals@eplus-claude-plugins
```

Verify: the skills list shows `rfi`, and with the `eplus-rfi-engine`
connection active, asking Claude to "review this RFI and draft a
response" runs the 4-step workflow and queries Hermes instead of
answering from memory.
